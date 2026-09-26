"""Exercise T18 check-in against the configured dev MySQL (AC-03–AC-05).

AC-03: submit from outside the geofence -> 422, no record written.
AC-04: foreign LBPH identity -> 403, no record written.
AC-05: full verified flow -> exactly one record with evidence and audit.

Real MySQL rows, schedule, LBPH training, and transactions; the camera frames
are mocked (as in smoke_t15/t16) because synthetic pixels carry no real face.
"""

from __future__ import annotations

from datetime import date
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


def _capture_pose(app, client, csrf: str, pose: str) -> None:
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


def _checkin_frames(app, client, csrf: str, challenge: str,
                    assessment) -> object:
    from app.services.face_enrollment_service import FrameAssessment as _FA

    last = None
    for eyes in (2, 0, 2):
        frame = _FA(True, "", eye_count=eyes, face_crop=assessment.face_crop.copy())
        with patch("app.services.attendance_service._inspect_frame",
                   return_value=frame):
            last = client.post(
                "/attendance/checkin/frame",
                data={"challenge_id": challenge,
                      "frame": (BytesIO(_jpeg_frame()), "checkin.jpg", "image/jpeg")},
                headers={"X-CSRF-Token": csrf},
            )
    return last


def _fake_geofence(allowed: bool, reason: str, **point):
    return lambda **_: {"allowed": allowed, "reason": reason,
                        "distance_meters": 5000.0 if not allowed else 10.0}


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="t18-smoke-") as temporary:
        app = create_app({"TESTING": True,
                          "STORAGE_ROOT": str(Path(temporary) / "private")})
        if app.config["APP_ENV"] == "production":
            raise SystemExit("Smoke T18 tidak boleh dijalankan pada environment production.")
        context = app.app_context()
        context.push()
        user_ids: list[int] = []
        student_ids: list[int] = []
        seed_ids: dict[str, int] = {}
        try:
            password_hash = generate_password_hash("SmokeTest1234567!")
            suffix = secrets.token_hex(4)

            with transaction() as (_, cursor):
                cursor.execute(
                    "INSERT INTO academic_years (name, start_date, end_date, is_active) VALUES (%s, '2026-07-01', '2027-06-30', 1)",
                    (f"Tahun {suffix}",))
                seed_ids["year"] = int(cursor.lastrowid)
                cursor.execute(
                    "INSERT INTO classes (academic_year_id, name, is_active) VALUES (%s, %s, 1)",
                    (seed_ids["year"], f"X-T18{suffix[:4]}"))
                seed_ids["class"] = int(cursor.lastrowid)
                cursor.execute(
                    "INSERT INTO attendance_schedules (academic_year_id, day_of_week, checkin_start, late_after, checkin_cutoff, checkout_start, is_active) VALUES (%s, %s, '00:00', '23:58', '23:59', '23:59', 1)",
                    (seed_ids["year"], date.today().isoweekday()))
                seed_ids["schedule"] = int(cursor.lastrowid)
                for index in range(2):
                    sfx = f"{suffix}{index}"
                    cursor.execute(
                        "INSERT INTO users (username, password_hash, role, is_active) VALUES (%s, %s, 'student', 1)",
                        (f"smoke_t18_{sfx}", password_hash))
                    uid = int(cursor.lastrowid)
                    user_ids.append(uid)
                    cursor.execute(
                        "INSERT INTO students (user_id, nisn, full_name, face_registered) VALUES (%s, %s, %s, 0)",
                        (uid, f"87{index}{sfx[:7]}", f"Smoke T18-{index}"))
                    sid = int(cursor.lastrowid)
                    student_ids.append(sid)
                    cursor.execute(
                        "INSERT INTO student_class_enrollments (student_id, academic_year_id, class_id) VALUES (%s, %s, %s)",
                        (sid, seed_ids["year"], seed_ids["class"]))

            # Real enrollment -> real per-student LBPH models for both students.
            clients = []
            for index in range(2):
                client, csrf = _login(app, user_ids[index], password_hash)
                for pose in POSES:
                    _capture_pose(app, client, csrf, pose)
                clients.append((client, csrf))

            # AC-03: outside the geofence -> 422 before any camera, no row.
            client, csrf = clients[0]
            with patch("app.services.attendance_service.evaluate_location",
                       side_effect=_fake_geofence(False, "outside")):
                denied = client.post("/attendance/checkin/start",
                                     json={"latitude": "0", "longitude": "0",
                                           "accuracy": "5"},
                                     headers={"X-CSRF-Token": csrf})
            assert denied.status_code == 422, denied.get_data(as_text=True)
            assert "luar area sekolah" in denied.json["error"]
            with get_db().cursor() as cursor:
                cursor.execute("SELECT COUNT(*) AS cnt FROM attendance_records WHERE student_id=%s",
                               (student_ids[0],))
                assert cursor.fetchone()["cnt"] == 0
            print("ac03_outside_rejected=ok; no_partial_row=ok")

            good_geo = patch("app.services.attendance_service.evaluate_location",
                             side_effect=_fake_geofence(True, "inside", **SCHOOL_POINT))
            gray_crop = np.full((100, 100, 3), 120, dtype=np.uint8)
            good_frame = FrameAssessment(True, "", eye_count=2, face_crop=gray_crop)

            # AC-04: foreign identity -> 403, no row for student 2.
            # _identity_match returns (matched: bool, distance: float).
            client2, csrf2 = clients[1]
            with good_geo:
                started = client2.post("/attendance/checkin/start",
                                       json=SCHOOL_POINT,
                                       headers={"X-CSRF-Token": csrf2})
            assert started.status_code == 200, started.get_data(as_text=True)
            with good_geo, patch("app.services.attendance_service._identity_match",
                                 return_value=(False, 120.0)):
                rejected = _checkin_frames(app, client2, csrf2,
                                           started.json["challenge_id"], good_frame)
            assert rejected.status_code == 403, rejected.get_data(as_text=True)
            assert "tidak cocok" in rejected.json["error"]
            with get_db().cursor() as cursor:
                cursor.execute("SELECT COUNT(*) AS cnt FROM attendance_records WHERE student_id=%s",
                               (student_ids[1],))
                assert cursor.fetchone()["cnt"] == 0
            print("ac04_foreign_identity_rejected=ok; no_partial_row=ok")

            # AC-05: full verified flow -> exactly one row + evidence + audit.
            with good_geo:
                started = client.post("/attendance/checkin/start",
                                      json=SCHOOL_POINT,
                                      headers={"X-CSRF-Token": csrf})
            assert started.status_code == 200, started.get_data(as_text=True)
            with good_geo:
                done = _checkin_frames(app, client, csrf,
                                       started.json["challenge_id"], good_frame)
            assert done.status_code == 200, done.get_data(as_text=True)
            assert done.json["captured"] is True
            assert done.json["status"] in ("Hadir", "Terlambat")
            with get_db().cursor() as cursor:
                cursor.execute(
                    """SELECT id, status, status_source, attendance_date, checkin_at, checkin_photo,
                              checkin_latitude, checkin_longitude, checkin_accuracy,
                              checkin_face_score, checkin_liveness_verified, class_id
                       FROM attendance_records WHERE student_id=%s""",
                    (student_ids[0],))
                rows = cursor.fetchall()
                assert len(rows) == 1, rows
                row = rows[0]
                assert row["checkin_at"] is not None
                assert row["status_source"] == "system"
                assert row["class_id"] == seed_ids["class"]
                assert row["checkin_liveness_verified"] == 1
                assert Path(temporary, "private", row["checkin_photo"]).is_file()
                assert row["checkin_photo"].endswith(".webp")
                cursor.execute(
                    """SELECT requires_attendance,source FROM attendance_day_snapshots
                       WHERE class_id=%s AND attendance_date=%s""",
                    (seed_ids["class"], row["attendance_date"]),
                )
                snapshot = cursor.fetchone()
                assert snapshot is not None and snapshot["requires_attendance"] == 1
                assert snapshot["source"] == "attendance_transaction"
                cursor.execute(
                    "SELECT action, metadata FROM audit_logs WHERE target_type='attendance_record' AND target_id=%s",
                    (row["id"],))
                audit = cursor.fetchone()
                assert audit is not None and audit["action"] == "attendance_checkin"
                assert '"is_late":' in str(audit["metadata"])
            print(f"ac05_checkin_committed=ok; status={done.json['status']}; evidence=webp; audit=ok")

            print("t18_smoke=ok; ac03=ok; ac04=ok; ac05=ok; cleanup=ok")
        finally:
            try:
                with transaction() as (_, cursor):
                    if seed_ids.get("class"):
                        cursor.execute(
                            "DELETE FROM attendance_day_snapshots WHERE class_id=%s",
                            (seed_ids["class"],))
                    if student_ids or user_ids:
                        sids = tuple(student_ids) if student_ids else (0,)
                        uids = tuple(user_ids) if user_ids else (0,)
                        placeholders_s = ",".join(["%s"] * len(sids))
                        placeholders_u = ",".join(["%s"] * len(uids))
                        cursor.execute("DELETE FROM attendance_records WHERE student_id IN (" + placeholders_s + ")", sids)
                        cursor.execute("DELETE FROM student_faces WHERE student_id IN (" + placeholders_s + ")", sids)
                        cursor.execute("DELETE FROM student_class_enrollments WHERE student_id IN (" + placeholders_s + ")", sids)
                        cursor.execute("DELETE FROM students WHERE id IN (" + placeholders_s + ")", sids)
                        cursor.execute("DELETE FROM audit_logs WHERE actor_user_id IN (" + placeholders_u + ")", uids)
                        cursor.execute("DELETE FROM face_enrollment_challenges WHERE user_id IN (" + placeholders_u + ")", uids)
                        cursor.execute("DELETE FROM users WHERE id IN (" + placeholders_u + ")", uids)
                        if seed_ids:
                            cursor.execute("DELETE FROM attendance_schedules WHERE academic_year_id=%s", (seed_ids["year"],))
                            cursor.execute("DELETE FROM schedule_exceptions WHERE academic_year_id=%s", (seed_ids["year"],))
                            cursor.execute("DELETE FROM classes WHERE academic_year_id=%s", (seed_ids["year"],))
                            cursor.execute("DELETE FROM academic_years WHERE id=%s", (seed_ids["year"],))
            finally:
                context.pop()


if __name__ == "__main__":
    main()
