"""Smoke protected evidence reads, teacher assignment changes, and private images."""

from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
import secrets
import tempfile

from PIL import Image
from werkzeug.security import generate_password_hash

from app import create_app
from app.database import transaction
from app.services.auth_service import credential_stamp
from app.services.storage_service import save_evidence


def _client(app, user_id: int, password_hash: str):
    client = app.test_client()
    with app.app_context(), client.session_transaction() as session:
        session["user_id"] = user_id
        session["credential_stamp"] = credential_stamp(password_hash)
        session["_csrf_token"] = secrets.token_urlsafe(24)
    return client


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="t23-evidence-") as temporary:
        app = create_app({"TESTING": True, "STORAGE_ROOT": str(Path(temporary) / "private")})
        if app.config["APP_ENV"] == "production":
            raise SystemExit("Smoke T23 hanya boleh memakai database development/test.")
        suffix = secrets.token_hex(4)
        password_hash = generate_password_hash(f"Synthetic-T23-{suffix}-password")
        user_ids: list[int] = []
        student_ids: list[int] = []
        teacher_ids: list[int] = []
        class_ids: list[int] = []
        year_id = None
        records: list[int] = []
        context = app.app_context()
        context.push()
        try:
            with transaction() as (_, cursor):
                for role, name in (("admin", "admin"), ("teacher", "satu"),
                                   ("teacher", "dua"), ("student", "berbukti"),
                                   ("student", "tanpa-snapshot")):
                    cursor.execute(
                        "INSERT INTO users (username,password_hash,role,is_active,must_change_password) VALUES (%s,%s,%s,1,0)",
                        (f"smoke-t23-{name}-{suffix}", password_hash, role),
                    )
                    user_ids.append(int(cursor.lastrowid))
                for index, user_id in enumerate(user_ids[1:3]):
                    cursor.execute(
                        "INSERT INTO teachers (user_id,full_name,employee_number) VALUES (%s,%s,%s)",
                        (user_id, f"Guru T23 {index} {suffix}", f"T23{suffix}{index}"),
                    )
                    teacher_ids.append(int(cursor.lastrowid))
                cursor.execute(
                    "INSERT INTO academic_years (name,start_date,end_date,is_active) VALUES (%s,%s,%s,1)",
                    (f"T23-{suffix}", date.today().replace(month=1, day=1), date.today().replace(month=12, day=31)),
                )
                year_id = int(cursor.lastrowid)
                for index, teacher_id in enumerate(teacher_ids):
                    cursor.execute(
                        "INSERT INTO classes (academic_year_id,name,teacher_id,is_active) VALUES (%s,%s,%s,1)",
                        (year_id, f"T23-{suffix}-{index}", teacher_id),
                    )
                    class_ids.append(int(cursor.lastrowid))
                for index, (user_id, class_id) in enumerate(zip(user_ids[3:], class_ids)):
                    cursor.execute(
                        "INSERT INTO students (user_id,nisn,full_name,face_registered) VALUES (%s,%s,%s,1)",
                        (user_id, f"T23{suffix}{index:02d}", f"Siswa T23 {index} {suffix}"),
                    )
                    student_id = int(cursor.lastrowid)
                    student_ids.append(student_id)
                    cursor.execute(
                        "INSERT INTO student_class_enrollments (student_id,academic_year_id,class_id) VALUES (%s,%s,%s)",
                        (student_id, year_id, class_id),
                    )

            image_key = save_evidence(Image.new("RGB", (32, 32), (115, 95, 180)))
            today = date.today()
            with transaction() as (_, cursor):
                cursor.execute(
                    """INSERT INTO attendance_records
                       (student_id,class_id,attendance_date,status,status_source,checkin_at,
                        checkin_latitude,checkin_longitude,checkin_accuracy,checkin_photo)
                       VALUES (%s,%s,%s,'present','system',%s,-5.12,97.15,9.5,%s)""",
                    (student_ids[0], class_ids[0], today, datetime.utcnow(), image_key),
                )
                records.append(int(cursor.lastrowid))
                cursor.execute(
                    """INSERT INTO attendance_records
                       (student_id,class_id,attendance_date,status,status_source,checkin_at)
                       VALUES (%s,NULL,%s,'present','system',%s)""",
                    (student_ids[1], today, datetime.utcnow()),
                )
                records.append(int(cursor.lastrowid))

            admin, teacher_one, teacher_two = (
                _client(app, user_ids[0], password_hash),
                _client(app, user_ids[1], password_hash),
                _client(app, user_ids[2], password_hash),
            )
            url = f"/attendance/{records[0]}/evidence"
            detail = teacher_one.get(url)
            assert detail.status_code == 200, detail.get_data(as_text=True)
            assert detail.headers.get("Cache-Control") == "no-store"
            detail_body = detail.get_data(as_text=True)
            assert "Lokasi diterima saat presensi" in detail_body
            assert "9.50" in detail_body and "-5.12" not in detail_body and "97.15" not in detail_body
            photo = teacher_one.get(f"{url}/checkin/image")
            assert photo.status_code == 200 and photo.mimetype == "image/webp"
            assert photo.headers.get("Cache-Control") == "no-store"
            assert photo.data.startswith(b"RIFF")
            photo.close()
            assert teacher_one.get(f"/attendance/{records[1]}/evidence").status_code == 404
            assert teacher_two.get(url).status_code == 404
            assert admin.get(url).status_code == 200

            with transaction() as (_, cursor):
                cursor.execute("UPDATE classes SET teacher_id=%s WHERE id=%s",
                               (teacher_ids[1], class_ids[0]))
            assert teacher_one.get(url).status_code == 404
            assert teacher_two.get(url).status_code == 200
            reassigned_photo = teacher_two.get(f"{url}/checkin/image")
            assert reassigned_photo.status_code == 200
            reassigned_photo.close()
            print("T23 MySQL smoke PASS: current assignment, snapshot scope, private image, no-store, admin access.")
        finally:
            try:
                with transaction() as (_, cursor):
                    if records:
                        cursor.execute("DELETE FROM attendance_records WHERE id IN (%s,%s)", tuple(records))
                    if student_ids:
                        cursor.execute("DELETE FROM student_class_enrollments WHERE student_id IN (%s,%s)", tuple(student_ids))
                        cursor.execute("DELETE FROM students WHERE id IN (%s,%s)", tuple(student_ids))
                    if class_ids:
                        cursor.execute("DELETE FROM classes WHERE id IN (%s,%s)", tuple(class_ids))
                    if year_id:
                        cursor.execute("DELETE FROM academic_years WHERE id=%s", (year_id,))
                    if teacher_ids:
                        cursor.execute("DELETE FROM teachers WHERE id IN (%s,%s)", tuple(teacher_ids))
                    if user_ids:
                        cursor.execute("DELETE FROM users WHERE id IN (%s,%s,%s,%s,%s)", tuple(user_ids))
            finally:
                context.pop()


if __name__ == "__main__":
    main()
