"""Exercise T15 challenge/capture persistence against the configured dev MySQL."""

from __future__ import annotations

from hashlib import sha256
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


def _jpeg_frame() -> bytes:
    output = BytesIO()
    Image.new("RGB", (120, 120), (120, 120, 120)).save(output, format="JPEG")
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
    with tempfile.TemporaryDirectory(prefix="t15-smoke-") as temporary:
        app = create_app({"TESTING": True,
                          "STORAGE_ROOT": str(Path(temporary) / "private")})
        if app.config["APP_ENV"] == "production":
            raise SystemExit("Smoke test hanya untuk database development/test.")

        suffix = secrets.token_hex(5)
        user_ids: list[int] = []
        password_hashes: list[str] = []
        context = app.app_context()
        context.push()
        try:
            with transaction() as (_, cursor):
                for index in range(2):
                    username = f"t15-{suffix}-{index}"
                    password_hash = generate_password_hash(f"synthetic-{suffix}-{index}")
                    cursor.execute(
                        """INSERT INTO users (username, password_hash, role, is_active, must_change_password)
                           VALUES (%s, %s, 'student', 1, 0)""",
                        (username, password_hash),
                    )
                    user_ids.append(int(cursor.lastrowid))
                    password_hashes.append(password_hash)
                    cursor.execute(
                        """INSERT INTO students (user_id, nisn, full_name, face_registered)
                           VALUES (%s, %s, %s, 0)""",
                        (user_ids[-1], f"96{suffix}{index}", f"Siswa Uji T15 {suffix}-{index}"),
                    )

            client, csrf = _login(app, user_ids[0], password_hashes[0])
            last_challenge = None
            for pose in POSES:
                last_challenge = _capture_pose(app, client, csrf, pose)

            with get_db().cursor() as cursor:
                cursor.execute("SELECT pose, storage_key FROM student_faces WHERE student_id=(SELECT id FROM students WHERE user_id=%s) ORDER BY pose",
                               (user_ids[0],))
                rows = cursor.fetchall()
                cursor.execute("SELECT face_registered FROM students WHERE user_id=%s", (user_ids[0],))
                registered = cursor.fetchone()["face_registered"]
            assert {row["pose"] for row in rows} == set(POSES)
            assert len(rows) == 3 and not registered
            assert all((Path(temporary) / "private" / row["storage_key"]).is_file() for row in rows)

            replay = client.post(
                "/face/enrollment/frame",
                data={"challenge_id": last_challenge,
                      "frame": (BytesIO(_jpeg_frame()), "camera.jpg", "image/jpeg")},
                headers={"X-CSRF-Token": csrf},
            )
            assert replay.status_code == 410

            cross_user_client, cross_csrf = _login(app, user_ids[1], password_hashes[1])
            challenge_response = client.post("/face/enrollment/challenge", json={"pose": "front"},
                                             headers={"X-CSRF-Token": csrf})
            cross_token = challenge_response.json["challenge_id"]
            assessment = FrameAssessment(True, "", eye_count=2,
                                         face_crop=np.full((100, 100, 3), 120, dtype=np.uint8))
            with patch(
                "app.services.face_enrollment_service._inspect_frame", return_value=assessment
            ):
                cross_user = cross_user_client.post(
                    "/face/enrollment/frame",
                    data={"challenge_id": cross_token,
                          "frame": (BytesIO(_jpeg_frame()), "camera.jpg", "image/jpeg")},
                    headers={"X-CSRF-Token": cross_csrf},
                )
            assert cross_user.status_code == 403

            expiry_response = client.post("/face/enrollment/challenge", json={"pose": "left"},
                                          headers={"X-CSRF-Token": csrf})
            expiry_token = expiry_response.json["challenge_id"]
            digest = sha256(expiry_token.encode("ascii")).hexdigest()
            with get_db().cursor() as cursor:
                cursor.execute("UPDATE face_enrollment_challenges SET expires_at=DATE_SUB(UTC_TIMESTAMP(6), INTERVAL 1 SECOND) WHERE challenge_hash=%s",
                               (digest,))
            get_db().commit()
            expired = client.post(
                "/face/enrollment/frame",
                data={"challenge_id": expiry_token,
                      "frame": (BytesIO(_jpeg_frame()), "camera.jpg", "image/jpeg")},
                headers={"X-CSRF-Token": csrf},
            )
            assert expired.status_code == 410

            print("t15_mysql_smoke=ok; three_unique_poses=ok; private_files=ok; gate_stays_false=ok; replay=410; cross_session=403; expiry=410; cleanup=ok")
        finally:
            try:
                with transaction() as (_, cursor):
                    if user_ids:
                        uid_tuple = tuple(user_ids)
                        placeholders = ",".join(["%s"] * len(uid_tuple))
                        cursor.execute("DELETE FROM face_enrollment_challenges WHERE user_id IN (" + placeholders + ")", uid_tuple)
                        cursor.execute("DELETE FROM student_faces WHERE student_id IN (SELECT id FROM students WHERE user_id IN (" + placeholders + "))", uid_tuple)
                        cursor.execute("DELETE FROM students WHERE user_id IN (" + placeholders + ")", uid_tuple)
                        cursor.execute("DELETE FROM audit_logs WHERE actor_user_id IN (" + placeholders + ")", uid_tuple)
                        cursor.execute("DELETE FROM users WHERE id IN (" + placeholders + ")", uid_tuple)
            finally:
                context.pop()


if __name__ == "__main__":
    main()
