"""End-to-end check-in and check-out submission: schedule, geofence, liveness, identity (T18–T19).

Order follows PRD 8.2: preflight proves eligibility and location before the
camera opens, then the frame loop proves liveness, and only a confirmed LBPH
identity may write attendance_records. The browser never decides any of it.
Check-out reuses the same order: preflight state/time, location, liveness,
identity, then update the existing record with checkout fields.
"""

from __future__ import annotations

from dataclasses import dataclass
import hmac
import secrets
import time
from typing import Any

import cv2
import numpy as np
from flask import current_app, session

from app.database import transaction
from app.services.attendance_state_service import load_day_context
from app.services.attendance_day_snapshot_service import ensure_day_snapshot
from app.services.audit_service import record_audit
from app.services.face_enrollment_service import (
    BLINK_PROMPTS,
    FrameAssessment,
    _inspect_frame,
    _next_stage,
)
from app.services.face_poc import FacePocError, load_student_model, predict_lbph
from app.services.geofence_service import evaluate_location
from app.services.schedule_service import can_checkout, evaluate_checkin
from app.services.storage_service import (
    StorageError,
    resolve_private_file,
    save_evidence,
)


CHECKIN_SESSION_KEY = "_attendance_checkin"
CHECKOUT_SESSION_KEY = "_attendance_checkout"
CHECKIN_TTL_SECONDS = 45
CHECKOUT_TTL_SECONDS = 45

# Location must be proven first (PRD 8.2 step 20-21) and stays bound to the
# challenge so a later frame cannot swap coordinates.
LOCATION_REASONS = {
    "not_configured": "Lokasi sekolah belum dikonfigurasi Admin. Hubungi Admin sekolah.",
    "accuracy_unreliable": "Akurasi lokasi kurang baik. Pindah ke tempat terbuka lalu coba lagi.",
    "invalid_location": "Lokasi tidak dapat dibaca. Aktifkan GPS lalu coba lagi.",
}


class AttendanceError(ValueError):
    """A safe check-in failure and its HTTP response status."""

    def __init__(self, message: str, status_code: int = 422) -> None:
        super().__init__(message)
        self.status_code = status_code


@dataclass(frozen=True)
class FrameResult:
    """One polled frame: either progress through blink or a final verdict."""

    captured: bool
    message: str
    stage: str
    result: dict[str, Any] | None = None


def _challenge_state() -> dict[str, Any]:
    state = session.get(CHECKIN_SESSION_KEY)
    if not isinstance(state, dict):
        raise AttendanceError("Sesi presensi belum dimulai. Muat ulang halaman lalu coba lagi.", 410)
    return state


def _store_challenge(token: str, *, latitude: Any, longitude: Any, accuracy: Any) -> None:
    session[CHECKIN_SESSION_KEY] = {
        "token": token,
        "stage": "await_open",
        "expires": time.monotonic() + CHECKIN_TTL_SECONDS,
        "latitude": str(latitude),
        "longitude": str(longitude),
        "accuracy": str(accuracy),
    }


def _clear_challenge() -> None:
    session.pop(CHECKIN_SESSION_KEY, None)


def _match_challenge(token: str) -> dict[str, Any]:
    state = _challenge_state()
    stored = state.get("token")
    if not isinstance(stored, str) or not isinstance(token, str) or not token:
        raise AttendanceError("Sesi presensi tidak valid. Muat ulang halaman lalu coba lagi.", 400)
    if not hmac.compare_digest(stored, token):
        raise AttendanceError("Sesi presensi tidak valid. Muat ulang halaman lalu coba lagi.", 400)
    if time.monotonic() > float(state.get("expires") or 0):
        _clear_challenge()
        raise AttendanceError("Sesi presensi kedaluwarsa. Mulai presensi lagi.", 410)
    return state


def start_checkin(user_id: int, *, latitude: Any, longitude: Any,
                  accuracy_meters: Any) -> dict[str, Any]:
    """Preflight: eligibility, enrollment, and location before the camera opens."""

    context = load_day_context(user_id)
    state = context["state"]
    student = context["student"]

    if not student["face_registered"] or not student["model_path"]:
        raise AttendanceError("Wajah belum terdaftar. Selesaikan pendaftaran wajah terlebih dahulu.", 409)
    if not state.get("can_checkin"):
        raise AttendanceError(state.get("reason") or "Check-in belum dapat dilakukan.", 409)

    location = evaluate_location(latitude=latitude, longitude=longitude,
                                 accuracy_meters=accuracy_meters)
    if not location["allowed"]:
        if location["reason"] == "outside":
            raise AttendanceError("Anda berada di luar area sekolah. Presensi hanya dapat dilakukan di lingkungan sekolah.", 422)
        raise AttendanceError(LOCATION_REASONS.get(location["reason"], "Lokasi tidak dapat divalidasi. Coba lagi."), 422)

    token = secrets.token_urlsafe(32)
    _store_challenge(token, latitude=latitude, longitude=longitude,
                     accuracy=accuracy_meters)
    return {
        "challenge_id": token,
        "expires_in": CHECKIN_TTL_SECONDS,
        "predicted_status": state.get("predicted_status"),
        "distance_meters": location.get("distance_meters"),
        "message": BLINK_PROMPTS["await_open"],
    }


def _identity_match(student_id: int, model_path: str,
                    crop: np.ndarray) -> tuple[bool, float]:
    """Compare the captured face against the stored model. Fail closed."""

    try:
        recognizer = load_student_model(model_path)
    except (StorageError, FileNotFoundError):
        current_app.logger.error(
            "attendance.identity_unavailable student_id=%s reason=model_missing", student_id)
        raise AttendanceError(
            "Model wajah tidak dapat dimuat. Presensi ditolak; hubungi Admin untuk memulihkan data wajah.", 503) from None
    except FacePocError:
        current_app.logger.error(
            "attendance.identity_unavailable student_id=%s reason=model_corrupt", student_id)
        raise AttendanceError(
            "Model wajah rusak. Presensi ditolak; hubungi Admin untuk memulihkan data wajah.", 503) from None

    try:
        label, distance = predict_lbph(recognizer, crop)
    except FacePocError:
        raise AttendanceError("Frame tidak dapat dikenali. Ambil ulang dengan wajah jelas.", 422) from None
    return label == student_id, float(distance)


def _store_record(*, user_id: int, student_id: int, academic_year_id: int | None,
                  class_id: int | None,
                  for_date: Any, assessment: FrameAssessment, distance: float,
                  challenge: dict[str, Any]) -> dict[str, Any]:
    """Write one check-in with its evidence; duplicate returns the existing row."""

    evidence_key: str | None = None
    try:
        with transaction() as (_, cursor):
            cursor.execute(
                """SELECT id, status, status_source, checkin_at, checkout_at, class_id
                   FROM attendance_records
                   WHERE student_id = %s AND attendance_date = %s
                   LIMIT 1 FOR UPDATE""",
                (student_id, for_date),
            )
            existing = cursor.fetchone()

            # Re-validate at write time: another tab or the clock may have moved
            # past the cutoff while the camera was open.
            revalidated = load_day_context(user_id)
            if not revalidated["state"].get("can_checkin"):
                if existing and existing["checkin_at"] is not None:
                    raise AttendanceError(
                        "Presensi masuk sudah tercatat sebelumnya.", 409)
                raise AttendanceError(
                    revalidated["state"].get("reason") or "Check-in tidak lagi diizinkan.", 409)

            if existing is not None and existing["checkin_at"] is not None:
                raise _DuplicateCheckin(existing)

            # Evidence is the exact crop that passed quality checks and that
            # LBPH just identified; compress it only after identity matched.
            assert assessment.face_crop is not None
            evidence_key = save_evidence(_crop_to_image(assessment.face_crop))

            evaluation = evaluate_checkin(revalidated["schedule"], revalidated["moment"])
            status = evaluation.get("status") or "present"
            coordinates = (
                float(np.clip(float(challenge["latitude"]), -90, 90)),
                float(np.clip(float(challenge["longitude"]), -180, 180)),
                float(challenge["accuracy"]),
            )
            face_score = round(distance, 4)
            if existing is None:
                cursor.execute(
                    """INSERT INTO attendance_records
                       (student_id, class_id, attendance_date, status, status_source,
                        checkin_at, checkin_latitude, checkin_longitude, checkin_accuracy,
                        checkin_photo, checkin_face_score, checkin_liveness_verified,
                        created_by, updated_by)
                       VALUES (%s, %s, %s, %s, 'system', UTC_TIMESTAMP(6),
                               %s, %s, %s, %s, %s, 1, %s, %s)""",
                    (student_id, class_id, for_date, status, *coordinates,
                     evidence_key, face_score, user_id, user_id),
                )
                record_id = int(cursor.lastrowid)
            else:
                cursor.execute(
                    """UPDATE attendance_records
                       SET status=%s, status_source='system', checkin_at=UTC_TIMESTAMP(6),
                           checkin_latitude=%s, checkin_longitude=%s, checkin_accuracy=%s,
                           checkin_photo=%s, checkin_face_score=%s, checkin_liveness_verified=1,
                           class_id=COALESCE(class_id, %s), updated_by=%s
                       WHERE id=%s""",
                    (status, *coordinates, evidence_key, face_score,
                     class_id, user_id, existing["id"]),
                )
                record_id = int(existing["id"])

            if academic_year_id is not None and class_id is not None:
                ensure_day_snapshot(
                    cursor, academic_year_id=int(academic_year_id), class_id=int(class_id),
                    for_date=for_date, schedule=revalidated["schedule"],
                    source="attendance_transaction",
                )

            record_audit(cursor, actor_user_id=user_id, action="attendance_checkin",
                         target_type="attendance_record", target_id=record_id,
                         metadata={"is_late": status == "late"})
    except BaseException:
        if evidence_key:
            _remove_private_file(evidence_key)
        raise

    return {
        "captured": True,
        "status": "Terlambat" if status == "late" else "Hadir",
        "message": "Presensi masuk berhasil dicatat.",
        "checkin": True,
        "record_id": record_id,
    }


class _DuplicateCheckin(AttendanceError):
    """Raised inside the transaction; answered with the existing row state."""

    def __init__(self, existing: dict[str, Any]) -> None:
        super().__init__("Presensi masuk sudah tercatat sebelumnya.", 409)
        self.existing = existing


def _remove_private_file(storage_key: str | None) -> None:
    if not storage_key:
        return
    try:
        resolve_private_file(storage_key).unlink(missing_ok=True)
    except (FileNotFoundError, OSError, StorageError):
        return


def _crop_to_image(crop: np.ndarray) -> "Image.Image":
    """BGR crop -> PIL for the compressed private evidence write."""

    from PIL import Image

    rgb = cv2.cvtColor(crop, cv2.COLOR_BGR2RGB)
    return Image.fromarray(rgb)


def process_checkin_frame(user_id: int, challenge_token: str,
                          payload: bytes, mime_type: str) -> FrameResult:
    """Advance liveness, then verify identity and persist the check-in."""

    state = _match_challenge(challenge_token)
    assessment = _inspect_frame(payload, mime_type)

    if not assessment.valid:
        # A rejected frame restarts liveness: the sequence must be continuous.
        state["stage"] = "await_open"
        session[CHECKIN_SESSION_KEY] = state
        return FrameResult(False, assessment.message, "await_open")

    stage = _next_stage(state["stage"], assessment.eye_count)
    if stage != "captured":
        state["stage"] = stage
        session[CHECKIN_SESSION_KEY] = state
        return FrameResult(False, BLINK_PROMPTS.get(stage, BLINK_PROMPTS["await_open"]), stage)

    # Blink sequence complete: identity must match this login before any write.
    context = load_day_context(user_id)
    student = context["student"]
    if not student["face_registered"] or not student["model_path"]:
        _clear_challenge()
        raise AttendanceError("Wajah tidak terdaftar lagi. Hubungi Admin untuk enrollment ulang.", 409)

    assert assessment.face_crop is not None
    matched, distance = _identity_match(int(student["student_id"]),
                                        str(student["model_path"]),
                                        assessment.face_crop)
    if not matched:
        _clear_challenge()
        raise AttendanceError(
            "Wajah tidak cocok dengan akun ini. Presensi ditolak.", 403)

    try:
        result = _store_record(
            user_id=user_id,
            student_id=int(student["student_id"]),
            academic_year_id=(int(context["academic_year_id"])
                              if context.get("academic_year_id") is not None else None),
            class_id=context["class_id"],
            for_date=context["for_date"],
            assessment=assessment,
            distance=distance,
            challenge=state,
        )
    except _DuplicateCheckin as duplicate:
        _clear_challenge()
        existing = duplicate.existing
        return FrameResult(True, "Presensi masuk sudah tercatat sebelumnya.", "captured", {
            "captured": True, "duplicate": True, "checkin": True,
            "status": ("Terlambat" if existing["status"] == "late" else "Hadir"),
            "message": str(duplicate),
        })
    except AttendanceError:
        _clear_challenge()
        raise

    _clear_challenge()
    return FrameResult(True, result["message"], "captured", result)


class _DuplicateCheckout(Exception):
    def __init__(self, existing: dict[str, Any]):
        self.existing = existing
        super().__init__("Presensi pulang sudah tercatat sebelumnya.")


def _checkout_challenge_state() -> dict[str, Any]:
    state = session.get(CHECKOUT_SESSION_KEY)
    if not isinstance(state, dict):
        raise AttendanceError(
            "Sesi presensi pulang belum dimulai. Muat ulang halaman lalu coba lagi.", 410)
    return state


def _store_checkout_challenge(token: str, *, latitude: Any, longitude: Any,
                              accuracy: Any) -> None:
    session[CHECKOUT_SESSION_KEY] = {
        "token": token,
        "stage": "await_open",
        "expires": time.monotonic() + CHECKOUT_TTL_SECONDS,
        "latitude": str(latitude),
        "longitude": str(longitude),
        "accuracy": str(accuracy),
    }


def _clear_checkout_challenge() -> None:
    session.pop(CHECKOUT_SESSION_KEY, None)


def _match_checkout_challenge(token: str) -> dict[str, Any]:
    state = _checkout_challenge_state()
    stored = state.get("token")
    if not isinstance(stored, str) or not isinstance(token, str) or not token:
        raise AttendanceError(
            "Sesi presensi pulang tidak valid. Muat ulang halaman lalu coba lagi.", 400)
    if not hmac.compare_digest(stored, token):
        raise AttendanceError(
            "Sesi presensi pulang tidak valid. Muat ulang halaman lalu coba lagi.", 400)
    if time.monotonic() > float(state.get("expires") or 0):
        _clear_checkout_challenge()
        raise AttendanceError("Sesi presensi pulang kedaluwarsa. Mulai presensi pulang lagi.", 410)
    return state


def start_checkout(user_id: int, *, latitude: Any, longitude: Any,
                   accuracy_meters: Any) -> dict[str, Any]:
    """Preflight for check-out: enrollment, state, and location before camera."""

    context = load_day_context(user_id)
    state = context["state"]
    student = context["student"]

    if not student["face_registered"] or not student["model_path"]:
        raise AttendanceError(
            "Wajah belum terdaftar. Selesaikan pendaftaran wajah terlebih dahulu.", 409)
    if not state.get("can_checkout_now"):
        raise AttendanceError(state.get("reason") or "Presensi pulang belum dapat dilakukan.", 409)

    location = evaluate_location(latitude=latitude, longitude=longitude,
                                 accuracy_meters=accuracy_meters)
    if not location["allowed"]:
        if location["reason"] == "outside":
            raise AttendanceError(
                "Anda berada di luar area sekolah. Presensi pulang hanya dapat dilakukan "
                "di lingkungan sekolah.", 422)
        raise AttendanceError(
            LOCATION_REASONS.get(location["reason"], "Lokasi tidak dapat divalidasi. Coba lagi."),
            422)

    token = secrets.token_urlsafe(32)
    _store_checkout_challenge(token, latitude=latitude, longitude=longitude,
                              accuracy=accuracy_meters)
    return {
        "challenge_id": token,
        "expires_in": CHECKOUT_TTL_SECONDS,
        "message": "Hadapkan satu wajah ke kamera untuk presensi pulang.",
    }


def process_checkout_frame(user_id: int, challenge_token: str, payload: bytes,
                           mimetype: str) -> FrameResult:
    """Advance check-out liveness and, on a verified identity, persist checkout."""

    state = _match_checkout_challenge(challenge_token)
    assessment = _inspect_frame(payload, mimetype)

    if not assessment.valid:
        # A rejected frame restarts liveness: the sequence must be continuous.
        state["stage"] = "await_open"
        session[CHECKOUT_SESSION_KEY] = state
        return FrameResult(False, assessment.message, "await_open")

    stage = _next_stage(state["stage"], assessment.eye_count)
    if stage != "captured":
        state["stage"] = stage
        session[CHECKOUT_SESSION_KEY] = state
        return FrameResult(False, BLINK_PROMPTS.get(stage, BLINK_PROMPTS["await_open"]), stage)

    # Blink complete: identity must match this login before any write.
    context = load_day_context(user_id)
    student = context["student"]
    if not student["face_registered"] or not student["model_path"]:
        _clear_checkout_challenge()
        raise AttendanceError("Wajah tidak terdaftar lagi. Hubungi Admin untuk enrollment ulang.", 409)

    assert assessment.face_crop is not None
    matched, distance = _identity_match(int(student["student_id"]),
                                        str(student["model_path"]),
                                        assessment.face_crop)
    if not matched:
        _clear_checkout_challenge()
        raise AttendanceError("Wajah tidak cocok dengan akun ini. Presensi pulang ditolak.", 403)

    try:
        result = _store_checkout_record(
            user_id=user_id,
            student_id=int(student["student_id"]),
            for_date=context["for_date"],
            assessment=assessment,
            distance=distance,
            challenge=state,
            schedule=context["schedule"],
            academic_year_id=(int(context["academic_year_id"])
                              if context.get("academic_year_id") is not None else None),
            class_id=(int(context["class_id"]) if context.get("class_id") is not None else None),
            at=context["moment"],
        )
    except _DuplicateCheckout as duplicate:
        _clear_checkout_challenge()
        return FrameResult(True, str(duplicate), "captured", {
            "captured": True, "duplicate": True, "checkout": True,
            "message": str(duplicate),
        })
    except AttendanceError:
        _clear_checkout_challenge()
        raise

    _clear_checkout_challenge()
    return FrameResult(True, result["message"], "captured", result)


def _store_checkout_record(*, user_id: int, student_id: int, for_date: Any,
                           assessment: FrameAssessment, distance: float,
                           challenge: dict[str, Any], schedule: dict[str, Any],
                           academic_year_id: int | None, class_id: int | None,
                           at: Any) -> dict[str, Any]:
    """Update checkout fields on the existing same-day record, atomically."""

    # Revalidate at write time so a race or clock change cannot slip through.
    if not schedule or not can_checkout(schedule, at):
        raise AttendanceError(
            "Presensi pulang belum dibuka. Tunggu jam pulang efektif.", 409)

    evidence_key: str | None = None
    try:
        with transaction() as (_, cursor):
            cursor.execute(
                "SELECT id, status, status_source, checkin_at, checkin_photo, "
                "checkin_face_score, checkout_at, class_id "
                "FROM attendance_records WHERE student_id=%s AND attendance_date=%s "
                "FOR UPDATE",
                (student_id, for_date),
            )
            row = cursor.fetchone()
            if row is None:
                raise AttendanceError("Presensi masuk belum tercatat. Check-in diperlukan sebelum presensi pulang.", 409)
            if row["checkin_at"] is None:
                raise AttendanceError("Presensi masuk belum tercatat. Check-in diperlukan sebelum presensi pulang.", 409)
            if row["checkout_at"] is not None:
                raise _DuplicateCheckout(row)

            assert assessment.face_crop is not None
            evidence_key = save_evidence(_crop_to_image(assessment.face_crop))

            # Coordinates come from the preflight challenge, never from the frame.
            try:
                lat = float(challenge["latitude"])
                lon = float(challenge["longitude"])
            except (KeyError, TypeError, ValueError):
                _remove_private_file(evidence_key)
                raise AttendanceError("Lokasi presensi pulang tidak valid. Ulangi presensi pulang.", 422) from None
            accuracy = float(challenge.get("accuracy") or 0)

            cursor.execute(
                "UPDATE attendance_records SET "
                "checkout_at=UTC_TIMESTAMP(6), checkout_latitude=%s, checkout_longitude=%s, "
                "checkout_accuracy=%s, checkout_photo=%s, checkout_face_score=%s, "
                "checkout_liveness_verified=%s, updated_by=%s "
                "WHERE id=%s AND checkout_at IS NULL",
                (lat, lon, accuracy, evidence_key, round(distance, 4),
                 True, user_id, row["id"]),
            )
            if cursor.rowcount != 1:
                _remove_private_file(evidence_key)
                evidence_key = None
                raise _DuplicateCheckout({"id": row["id"], "status": row["status"]})

            if academic_year_id is not None and class_id is not None:
                ensure_day_snapshot(
                    cursor, academic_year_id=academic_year_id, class_id=class_id,
                    for_date=for_date, schedule=schedule,
                    source="attendance_transaction",
                )

            record_audit(
                cursor,
                actor_user_id=user_id,
                action="attendance_checkout",
                target_type="attendance_record",
                target_id=int(row["id"]),
                metadata={"duplicate": False},
            )
    except _DuplicateCheckout:
        if evidence_key:
            _remove_private_file(evidence_key)
        raise
    except AttendanceError:
        if evidence_key:
            _remove_private_file(evidence_key)
        raise
    except BaseException:
        if evidence_key:
            _remove_private_file(evidence_key)
        raise

    return {
        "captured": True,
        "checkout": True,
        "message": "Presensi pulang berhasil dicatat.",
    }
