"""Server-validated, student-owned capture for the three enrollment poses."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import tempfile
from typing import Any

import cv2
import numpy as np

from app.database import transaction
from app.services.audit_service import record_audit
from app.services.enrollment_service import POSE_LABELS, POSE_ORDER
from app.services.face_poc import (
    PROVISIONAL_BRIGHTNESS_MAX,
    PROVISIONAL_BRIGHTNESS_MIN,
    FacePocError,
    assess_image_quality,
    detect_eye_count,
    detect_single_face,
    preprocess_face,
    train_lbph,
)
from app.services.storage_service import (
    StorageError,
    resolve_private_file,
    save_camera_image,
    save_trained_model,
    validate_camera_image,
)


EYES_OPEN_MESSAGE = (
    "Mata tidak terlihat. Buka mata lebar menghadap kamera, lalu ambil foto lagi."
)
BLINK_PROMPTS = {
    "await_open": "Lihat kamera dan buka mata.",
    "await_closed": "Sekarang kedip satu kali.",
    "await_reopen": "Buka mata kembali.",
}


class FaceEnrollmentError(ValueError):
    """A safe enrollment error and its HTTP response status."""

    def __init__(self, message: str, status_code: int = 422) -> None:
        super().__init__(message)
        self.status_code = status_code


@dataclass(frozen=True)
class FrameAssessment:
    """One decoded camera frame after server-side face/quality inspection."""

    valid: bool
    message: str
    eye_count: int = 0
    face_crop: np.ndarray | None = None


def _student_row(cursor: Any, user_id: int) -> dict[str, Any]:
    cursor.execute(
        """SELECT s.id, s.face_registered
           FROM students AS s JOIN users AS u ON u.id=s.user_id
           WHERE u.id=%s AND u.role='student' AND u.is_active=1
           LIMIT 1 FOR UPDATE""",
        (user_id,),
    )
    student = cursor.fetchone()
    if student is None:
        raise FaceEnrollmentError("Profil Siswa tidak ditemukan.", 404)
    if bool(student["face_registered"]):
        raise FaceEnrollmentError("Pendaftaran wajah sudah selesai.", 409)
    return student


def _inspect_frame(payload: bytes, mime_type: str) -> FrameAssessment:
    try:
        with validate_camera_image(payload, mime_type) as decoded:
            frame = cv2.cvtColor(np.asarray(decoded), cv2.COLOR_RGB2BGR)
    except StorageError as error:
        raise FaceEnrollmentError(str(error), 422) from None

    try:
        x, y, width, height = detect_single_face(frame)
        crop = frame[y:y + height, x:x + width]
        quality = assess_image_quality(crop)
        if not quality.acceptable:
            if quality.brightness < PROVISIONAL_BRIGHTNESS_MIN:
                message = "Wajah terlalu gelap. Tambah cahaya lalu tahan kamera stabil."
            elif quality.brightness > PROVISIONAL_BRIGHTNESS_MAX:
                message = "Wajah terlalu terang. Kurangi cahaya langsung ke kamera."
            else:
                message = "Wajah tampak buram. Tahan kamera lebih stabil."
            return FrameAssessment(False, message)
        eyes = detect_eye_count(crop)
        return FrameAssessment(True, "Wajah terdeteksi.", eyes, crop.copy())
    except FacePocError:
        return FrameAssessment(
            False,
            "Pastikan hanya satu wajah berada di tengah kamera dan terlihat jelas.",
        )
    except cv2.error:
        return FrameAssessment(False, "Frame kamera gagal diproses. Coba tahan perangkat lebih stabil.")


def _next_stage(stage: str, eye_count: int) -> str:
    """Advance only from server-observed open/closed/open eye-state frames.

    Shared by the attendance check-in/check-out blink flow. Enrollment uses
    manual capture and does not call this helper.
    """

    eyes_open = eye_count >= 1
    if stage == "await_open" and eyes_open:
        return "await_closed"
    if stage == "await_closed" and eye_count == 0:
        return "await_reopen"
    if stage == "await_reopen" and eyes_open:
        return "captured"
    return stage


def _remove_private_file(storage_key: str | None) -> None:
    if not storage_key:
        return
    try:
        resolve_private_file(storage_key).unlink(missing_ok=True)
    except (FileNotFoundError, OSError, StorageError):
        # The DB is authoritative; a failed cleanup leaves only a private orphan.
        return


def _save_face_crop(crop: np.ndarray) -> str:
    encoded_ok, encoded = cv2.imencode(".png", crop)
    if not encoded_ok:
        raise FaceEnrollmentError("Sampel wajah tidak dapat disimpan. Coba pose lagi.", 503)
    return save_camera_image("faces", encoded.tobytes(), "image/png")


def _upsert_pose_crop(cursor: Any, student_id: int, pose: str,
                      storage_key: str) -> tuple[str | None, list[str]]:
    """Replace any previous sample for the pose and list all saved poses."""

    cursor.execute(
        """SELECT storage_key FROM student_faces
           WHERE student_id=%s AND pose=%s LIMIT 1 FOR UPDATE""",
        (student_id, pose),
    )
    old = cursor.fetchone()
    previous_storage_key = old["storage_key"] if old else None
    if old:
        cursor.execute(
            """UPDATE student_faces SET storage_key=%s
               WHERE student_id=%s AND pose=%s""",
            (storage_key, student_id, pose),
        )
    else:
        cursor.execute(
            """INSERT INTO student_faces (student_id, pose, storage_key)
               VALUES (%s, %s, %s)""",
            (student_id, pose, storage_key),
        )
    cursor.execute(
        """SELECT pose FROM student_faces WHERE student_id=%s
           ORDER BY FIELD(pose, 'front', 'left', 'right')""",
        (student_id,),
    )
    saved_poses = [row["pose"] for row in cursor.fetchall()]
    return previous_storage_key, saved_poses


def _train_and_finalize(cursor: Any, *, actor_user_id: int, student_id: int) -> str:
    """Train LBPH from the three enrollment faces and mark enrollment done."""

    record_audit(
        cursor,
        actor_user_id=actor_user_id,
        action="face_enrollment_completed",
        target_type="student",
        target_id=student_id,
    )
    cursor.execute(
        """SELECT sf.storage_key, sf.pose FROM student_faces AS sf
           WHERE sf.student_id=%s
           ORDER BY FIELD(sf.pose, 'front', 'left', 'right')""",
        (student_id,),
    )
    face_rows = cursor.fetchall()
    images = []
    for row in face_rows:
        face_path = resolve_private_file(row["storage_key"])
        bgr = cv2.imread(str(face_path))
        if bgr is None:
            raise FaceEnrollmentError(
                f"Gambar pose {POSE_LABELS[row['pose']].lower()} tidak dapat dibaca. Ambil ulang.", 422
            )
        images.append(bgr)
    label_array = np.full(len(images), int(student_id), dtype=np.int32)
    recognizer = train_lbph(images, label_array)
    with tempfile.NamedTemporaryFile(suffix=".yml", delete=False) as tmp:
        tmp_path = tmp.name
    try:
        recognizer.save(tmp_path)
        model_bytes = Path(tmp_path).read_bytes()
    finally:
        Path(tmp_path).unlink(missing_ok=True)
    model_key = save_trained_model(model_bytes)
    cursor.execute(
        """UPDATE students SET face_registered=TRUE, model_path=%s
           WHERE id=%s""",
        (model_key, student_id),
    )
    return model_key


def capture_enrollment_pose(user_id: int, pose: str,
                            payload: bytes, mime_type: str) -> dict[str, Any]:
    """Validate one manually captured frame and store it for the requested pose.

    Manual capture checks a single face, image quality, and visibly open eyes
    on the submitted still frame. There is no temporal blink sequence.
    """

    if pose not in POSE_ORDER:
        raise FaceEnrollmentError("Pose pengambilan tidak valid.", 400)
    assessment = _inspect_frame(payload, mime_type)
    if not assessment.valid:
        raise FaceEnrollmentError(assessment.message, 422)
    if assessment.eye_count < 1:
        raise FaceEnrollmentError(EYES_OPEN_MESSAGE, 422)
    assert assessment.face_crop is not None

    new_storage_key = None
    previous_storage_key = None
    model_key = None
    try:
        with transaction() as (_, cursor):
            student = _student_row(cursor, user_id)
            new_storage_key = _save_face_crop(assessment.face_crop)
            previous_storage_key, saved_poses = _upsert_pose_crop(
                cursor, student["id"], pose, new_storage_key
            )
            record_audit(
                cursor,
                actor_user_id=user_id,
                action="face_pose_captured",
                target_type="student",
                target_id=student["id"],
                metadata={"face_registered": len(saved_poses) >= 3},
            )
            if len(saved_poses) >= 3:
                model_key = _train_and_finalize(
                    cursor, actor_user_id=user_id, student_id=student["id"]
                )
    except Exception:
        _remove_private_file(new_storage_key)
        _remove_private_file(model_key)
        raise

    _remove_private_file(previous_storage_key)
    result: dict[str, Any] = {
        "captured": True,
        "pose": pose,
        "pose_label": POSE_LABELS[pose],
        "saved_poses": saved_poses,
        "saved_count": len(saved_poses),
        "message": f"Pose {POSE_LABELS[pose].lower()} berhasil disimpan.",
    }
    if len(saved_poses) >= 3:
        result["enrollment_complete"] = True
        result["message"] = "Pendaftaran wajah berhasil! Silakan login kembali."
        result["redirect"] = "/login"
    return result
