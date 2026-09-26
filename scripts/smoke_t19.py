"""Exercise T19 check-out against the configured dev MySQL (AC-06, AC-07, AC-11).

AC-06: checked-in but before checkout_start -> server rejects checkout (409), no write.
AC-07: checked-in and time >= checkout_start -> same record receives checkout_at.
AC-11: class-specific early dismissal -> schedule exception drives checkout_start.

Real MySQL rows, schedule, exception, enrollment, and transactions; camera frames
are mocked (as in smoke_t15/t16/t18) because synthetic pixels carry no real face.
"""

from __future__ import annotations

from datetime import date, datetime
from io import BytesIO
from pathlib import Path
import secrets
import tempfile
from unittest.mock import patch

import numpy as np
from PIL import Image
from werkzeug.security import generate_password_hash

from app import create_app
from app.database import get_db, transaction
from app.services.auth_service import credential_stamp
from app.services.face_enrollment_service import FrameAssessment


POSES = ("front", "left", "right")
SCHOOL_POINT = {"latitude": "-5.5", "longitude": "95.3", "accuracy": "5"}


def _jpeg_frame() -> bytes:
    output = BytesIO()
    Image.new("RGB", (200, 200), (120, 120, 120)).save(output, format="JPEG")
    return output.getvalue()


def _login(app, user_id: int, password_hash: str):
    client = app.test_client()
    csrf = secrets.token_urlsafe(24)
    with app.app_context(), client.session_transaction() as session:
        session["user_id"] = user_id
        session["credential_stamp"] = credential_stamp(password_hash)
        session["_csrf_token"] = csrf
    return client, csrf


def _capture_pose(client, csrf: str, pose: str) -> None:
    response = client.post("/face/enrollment/challenge", json={"pose": pose},
                           headers={"X-CSRF-Token": csrf})
    assert response.status_code == 200, response.get_data(as_text=True)
    challenge = response.json["challenge_id"]
    fake_crop = np.full((100, 100, 3), 120, dtype=np.uint8)
    for eyes in (2, 0, 2):
        assessment = FrameAssessment(True, "", eye_count=eyes, face_crop=fake_crop)
        with patch("app.services.face_enrollment_service._inspect_frame",
                   return_value=assessment):
            response = client.post(
                "/face/enrollment/frame",
                data={"challenge_id": challenge,
                      "frame": (BytesIO(_jpeg_frame()), "camera.jpg", "image/jpeg")},
                headers={"X-CSRF-Token": csrf},
            )
        assert response.status_code == 200, response.get_data(as_text=True)
    assert response.json["captured"] is True, response.json


def _checkin(client, csrf: str) -> dict:
    """Complete a real check-in so checkout has a valid same-day record."""
    gray_crop = np.full((100, 100, 3), 120, dtype=np.uint8)
    with patch("app.services.attendance_service.evaluate_location",
               side_effect=lambda **_: {"allowed": True, "reason": "inside",
                                        "distance_meters": 10.0}):
        started = client.post("/attendance/checkin/start", json=SCHOOL_POINT,
                              headers={"X-CSRF-Token": csrf})
        assert started.status_code == 200, started.get_data(as_text=True)
        challenge = started.json["challenge_id"]
        for eyes in (2, 0, 2):
            frame = FrameAssessment(True, "", eye_count=eyes, face_crop=gray_crop.copy())
            with patch("app.services.attendance_service._inspect_frame",
                       return_value=frame):
                last = client.post(
                    "/attendance/checkin/frame",
                    data={"challenge_id": challenge,
                          "frame": (BytesIO(_jpeg_frame()), "checkin.jpg", "image/jpeg")},
                    headers={"X-CSRF-Token": csrf},
                )
    assert last.status_code == 200, last.get_data(as_text=True)
    assert last.json["captured"] is True, last.json
    return last.json


def _checkout(client, csrf: str) -> tuple[int, dict | None]:
    gray_crop = np.full((100, 100, 3), 120, dtype=np.uint8)
    with patch("app.services.attendance_service.evaluate_location",
               side_effect=lambda **_: {"allowed": True, "reason": "inside",
                                        "distance_meters": 10.0}):
        started = client.post("/attendance/checkout/start", json=SCHOOL_POINT,
                              headers={"X-CSRF-Token": csrf})
        if started.status_code != 200:
            return started.status_code, started.json
        challenge = started.json["challenge_id"]
        for eyes in (2, 0, 2):
            frame = FrameAssessment(True, "", eye_count=eyes, face_crop=gray_crop.copy())
            with patch("app.services.attendance_service._inspect_frame",
                       return_value=frame):
                last = client.post(
                    "/attendance/checkout/frame",
                    data={"challenge_id": challenge,
                          "frame": (BytesIO(_jpeg_frame()), "checkout.jpg", "image/jpeg")},
                    headers={"X-CSRF-Token": csrf},
                )
    return last.status_code, last.json


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="t19-smoke-") as temporary:
        app = create_app({"TESTING": True,
                          "STORAGE_ROOT": str(Path(temporary) / "private")})
        if app.config["APP_ENV"] == "production":
            raise SystemExit("Smoke T19 tidak boleh dijalankan pada environment production.")
        context = app.app_context()
        context.push()
        user_id: int | None = None
        student_id: int | None = None
        seed_ids: dict[str, int] = {}
        try:
            password_hash = generate_password_hash("SmokeTest1234567!")
            suffix = secrets.token_hex(4)
            today = date.today()
            # Regular schedule: checkout at 23:59 (after now) so early checkout fails (AC-06).
            with transaction() as (_, cursor):
                cursor.execute(
                    "INSERT INTO academic_years (name, start_date, end_date, is_active) VALUES (%s, '2026-07-01', '2027-06-30', 1)",
                    (f"Tahun T19 {suffix}",))
                seed_ids["year"] = int(cursor.lastrowid)
                cursor.execute(
                    "INSERT INTO classes (academic_year_id, name, is_active) VALUES (%s, %s, 1)",
                    (seed_ids["year"], f"X-T19{suffix[:4]}"))
                seed_ids["class"] = int(cursor.lastrowid)
                cursor.execute(
                    "INSERT INTO attendance_schedules (academic_year_id, day_of_week, checkin_start, late_after, checkin_cutoff, checkout_start, is_active) VALUES (%s, %s, '00:00', '23:58', '23:59', '23:59', 1)",
                    (seed_ids["year"], today.isoweekday()))
                seed_ids["schedule"] = int(cursor.lastrowid)
                cursor.execute(
                    "INSERT INTO users (username, password_hash, role, is_active) VALUES (%s, %s, 'student', 1)",
                    (f"smoke_t19_{suffix}", password_hash))
                user_id = int(cursor.lastrowid)
                cursor.execute(
                    "INSERT INTO students (user_id, nisn, full_name, face_registered) VALUES (%s, %s, %s, 0)",
                    (user_id, f"91{suffix}", "Smoke T19"))
                student_id = int(cursor.lastrowid)
                cursor.execute(
                    "INSERT INTO student_class_enrollments (student_id, academic_year_id, class_id) VALUES (%s, %s, %s)",
                    (student_id, seed_ids["year"], seed_ids["class"]))

            client, csrf = _login(app, user_id, password_hash)
            for pose in POSES:
                _capture_pose(client, csrf, pose)

            # Check-in first so checkout has a same-day record.
            _checkin(client, csrf)

            # AC-06: checked-in but checkout_start=23:59 (future) -> 409, no write.
            status, body = _checkout(client, csrf)
            assert status == 409, (status, body)
            assert "mulai 23:59" in body["error"], body
            assert body["retry"] is False, body
            with get_db().cursor() as cursor:
                cursor.execute(
                    "SELECT checkout_at FROM attendance_records WHERE student_id=%s",
                    (student_id,))
                row = cursor.fetchone()
                assert row is not None and row["checkout_at"] is None, row
            print("ac06_early_checkout_rejected=ok; no_checkout_write=ok")

            # AC-11: class-specific early dismissal exception overrides checkout_start=00:00.
            # All four times are set because the resolver requires a non-decreasing
            # order across inherited + overridden fields (23:59 > 00:00 would fail).
            with transaction() as (_, cursor):
                cursor.execute(
                    """INSERT INTO schedule_exceptions
                       (academic_year_id, exception_date, scope, class_id, exception_type,
                        checkin_start, late_after, checkin_cutoff, checkout_start, is_active)
                       VALUES (%s, %s, 'class', %s, 'early_dismissal',
                               '00:00', '00:00', '00:00', '00:00', 1)""",
                    (seed_ids["year"], today.isoformat(), seed_ids["class"]))

            status, body = _checkout(client, csrf)
            assert status == 200, (status, body)
            assert body["captured"] is True, body
            assert body["checkout"] is True, body
            with get_db().cursor() as cursor:
                cursor.execute(
                    """SELECT id, checkin_at, checkout_at, checkout_photo,
                              checkout_latitude, checkout_longitude, checkout_accuracy,
                              checkout_face_score, checkout_liveness_verified, class_id
                       FROM attendance_records WHERE student_id=%s""",
                    (student_id,))
                rows = cursor.fetchall()
                assert len(rows) == 1, rows  # Same record, no insert.
                row = rows[0]
                # AC-07: same record received checkout_at + evidence.
                assert row["checkout_at"] is not None, row
                assert row["checkin_at"] is not None, row
                assert row["checkout_liveness_verified"] == 1, row
                assert row["checkout_photo"].endswith(".webp"), row
                assert Path(temporary, "private", row["checkout_photo"]).is_file()
                assert row["class_id"] == seed_ids["class"], row
                cursor.execute(
                    "SELECT action FROM audit_logs WHERE target_type='attendance_record' AND target_id=%s AND action='attendance_checkout'",
                    (row["id"],))
                assert cursor.fetchone() is not None, "audit attendance_checkout missing"
            print("ac11_early_dismissal_exception_used=ok; ac07_same_record_checkout=ok; audit=ok")

            # Duplicate checkout -> returns duplicate without a second write.
            status, body = _checkout(client, csrf)
            assert status == 409, (status, body)
            with get_db().cursor() as cursor:
                cursor.execute("SELECT COUNT(*) AS cnt FROM attendance_records WHERE student_id=%s",
                               (student_id,))
                assert cursor.fetchone()["cnt"] == 1, "duplicate checkout inserted a row"
            print("duplicate_checkout_idempotent=ok")

            print("t19_smoke=ok; ac06=ok; ac07=ok; ac11=ok; duplicate=ok; cleanup=ok")
        finally:
            try:
                if user_id is not None or student_id is not None:
                    with transaction() as (_, cursor):
                        if seed_ids.get("class"):
                            cursor.execute(
                                "DELETE FROM attendance_day_snapshots WHERE class_id=%s",
                                (seed_ids["class"],))
                        if student_id is not None:
                            cursor.execute("DELETE FROM attendance_records WHERE student_id=%s", (student_id,))
                            cursor.execute("DELETE FROM student_faces WHERE student_id=%s", (student_id,))
                            cursor.execute("DELETE FROM student_class_enrollments WHERE student_id=%s", (student_id,))
                            cursor.execute("DELETE FROM students WHERE id=%s", (student_id,))
                        if user_id is not None:
                            cursor.execute("DELETE FROM audit_logs WHERE actor_user_id=%s", (user_id,))
                            cursor.execute("DELETE FROM face_enrollment_challenges WHERE user_id=%s", (user_id,))
                            cursor.execute("DELETE FROM users WHERE id=%s", (user_id,))
                        if seed_ids:
                            cursor.execute("DELETE FROM attendance_schedules WHERE academic_year_id=%s", (seed_ids["year"],))
                            cursor.execute("DELETE FROM schedule_exceptions WHERE academic_year_id=%s", (seed_ids["year"],))
                            cursor.execute("DELETE FROM classes WHERE academic_year_id=%s", (seed_ids["year"],))
                            cursor.execute("DELETE FROM academic_years WHERE id=%s", (seed_ids["year"],))
            finally:
                context.pop()


if __name__ == "__main__":
    main()
