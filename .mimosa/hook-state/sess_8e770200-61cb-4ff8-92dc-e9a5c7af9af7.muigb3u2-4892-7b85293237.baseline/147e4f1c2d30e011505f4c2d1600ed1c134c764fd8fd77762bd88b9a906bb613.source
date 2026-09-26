"""Exercise T16 model training, enrollment finalization, and face reset against the configured dev MySQL."""

from __future__ import annotations

from hashlib import sha256
from io import BytesIO
from pathlib import Path
import secrets
import tempfile
from unittest.mock import patch

import cv2
import numpy as np
from PIL import Image
from werkzeug.security import generate_password_hash

from app import create_app
from app.database import get_db, transaction
from app.services.auth_service import credential_stamp
from app.services.face_enrollment_service import FrameAssessment


POSES = ("front", "left", "right")


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


def _capture_pose(app, client, csrf: str, pose: str) -> str:
    response = client.post("/face/enrollment/challenge", json={"pose": pose},
                           headers={"X-CSRF-Token": csrf})
    assert response.status_code == 200, response.get_data(as_text=True)
    challenge = response.json["challenge_id"]
    fake_crop = np.full((100, 100, 3), 120, dtype=np.uint8)
    for eyes in (2, 0, 2):
        assessment = FrameAssessment(True, "", eye_count=eyes, face_crop=fake_crop)
        with patch(
            "app.services.face_enrollment_service._inspect_frame", return_value=assessment
        ):
            response = client.post(
                "/face/enrollment/frame",
                data={"challenge_id": challenge,
                      "frame": (BytesIO(_jpeg_frame()), "camera.jpg", "image/jpeg")},
                headers={"X-CSRF-Token": csrf},
            )
        assert response.status_code == 200, response.get_data(as_text=True)
    assert response.json["captured"] is True, response.json
    assert response.json["pose"] == pose
    return challenge


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="t16-smoke-") as temporary:
        app = create_app({"TESTING": True,
                          "STORAGE_ROOT": str(Path(temporary) / "private")})
        if app.config["APP_ENV"] == "production":
            raise SystemExit("Smoke T16 tidak boleh dijalankan pada environment production.")
        context = app.app_context()
        context.push()
        user_ids = []
        try:
            password_hash = generate_password_hash("SmokeTest1234567!")
            suffix = secrets.token_hex(4)

            # Create 2 test students
            with transaction() as (_, cursor):
                for index in range(2):
                    sfx = f"{suffix}{index}"
                    cursor.execute(
                        "INSERT INTO users (username, password_hash, role, is_active) VALUES (%s, %s, 'student', 1)",
                        (f"smoke_t16_{sfx}", password_hash))
                    uid = cursor.lastrowid
                    user_ids.append(uid)
                    cursor.execute(
                        "INSERT INTO students (user_id, nisn, full_name, face_registered) VALUES (%s, %s, %s, 0)",
                        (uid, f"88{index}{sfx[:7]}", f"Smoke T16-{index}"))

            # Student 1: enroll all 3 poses → training → enrollment_complete
            client1, csrf1 = _login(app, user_ids[0], password_hash)
            for pose in POSES:
                _capture_pose(app, client1, csrf1, pose)
            # The third pose triggers training and enrollment_complete
            # Verify student has model_path and face_registered
            with get_db().cursor() as cursor:
                cursor.execute(
                    "SELECT face_registered, model_path FROM students WHERE user_id=%s",
                    (user_ids[0],))
                row = cursor.fetchone()
                assert row["face_registered"] == 1, f"face_registered should be 1, got {row['face_registered']}"
                assert row["model_path"] is not None, "model_path should not be None"
                model_path = row["model_path"]

            # Verify model loads
            from app.services.face_poc import load_student_model
            recognizer = load_student_model(model_path)
            assert recognizer is not None, "Recognizer should load successfully"

            # Student 1: reset face
            admin_client, admin_csrf = _login(app, user_ids[1], password_hash)
            # Create an admin user for reset
            with transaction() as (_, cursor):
                cursor.execute(
                    "INSERT INTO users (username, password_hash, role, is_active) VALUES (%s, %s, 'admin', 1)",
                    (f"smoke_t16_adm_{suffix}", password_hash))
                admin_uid = cursor.lastrowid
                cursor.execute(
                    "INSERT INTO students (user_id, nisn, full_name, face_registered) VALUES (%s, %s, 'Admin Smoke', 0)",
                    (admin_uid, f"99{suffix[:8]}"))
                user_ids.append(admin_uid)
                # Get student_id for user_ids[0]
                cursor.execute("SELECT id AS student_id FROM students WHERE user_id=%s", (user_ids[0],))
                target_student_id = cursor.fetchone()["student_id"]
            admin_client2, admin_csrf2 = _login(app, admin_uid, password_hash)
            response = admin_client2.post(
                f"/admin/students/{target_student_id}/reset-face",
                headers={"X-CSRF-Token": admin_csrf2})
            assert response.status_code in (302, 200), response.get_data(as_text=True)

            # Verify reset
            with get_db().cursor() as cursor:
                cursor.execute(
                    "SELECT face_registered, model_path FROM students WHERE user_id=%s",
                    (target_student_id,))
                row = cursor.fetchone()
                assert row["face_registered"] == 0, "face_registered should be 0 after reset"
                assert row["model_path"] is None, "model_path should be None after reset"
                cursor.execute(
                    "SELECT COUNT(*) AS cnt FROM student_faces WHERE student_id=%s",
                    (target_student_id,))
                assert cursor.fetchone()["cnt"] == 0, "student_faces should be empty after reset"

            print("t16_smoke=ok; training=ok; model_load=ok; reset=ok; cleanup=ok")
        finally:
            try:
                with transaction() as (_, cursor):
                    if user_ids:
                        uid_tuple = tuple(user_ids)
                        placeholders = ",".join(["%s"] * len(uid_tuple))
                        cursor.execute("DELETE FROM audit_logs WHERE actor_user_id IN (" + placeholders + ")", uid_tuple)
                        cursor.execute("DELETE FROM student_faces WHERE student_id IN (SELECT id FROM students WHERE user_id IN (" + placeholders + "))", uid_tuple)
                        cursor.execute("DELETE FROM students WHERE user_id IN (" + placeholders + ")", uid_tuple)
                        cursor.execute("DELETE FROM users WHERE id IN (" + placeholders + ")", uid_tuple)
            finally:
                context.pop()


if __name__ == "__main__":
    main()
