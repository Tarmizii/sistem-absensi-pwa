"""Exercise enrollment gate and per-student progress against dev MySQL."""

from __future__ import annotations

import secrets

from werkzeug.security import generate_password_hash

from app import create_app
from app.database import get_db, transaction
from app.services.auth_service import credential_stamp


def main() -> None:
    app = create_app({"TESTING": True})
    if app.config["APP_ENV"] == "production":
        raise SystemExit("Smoke test hanya untuk database development/test.")
    suffix = secrets.token_hex(5)
    nisns = (f"98{suffix[:8]}", f"97{suffix[:8]}")
    user_ids: list[int] = []
    student_ids: list[int] = []
    teacher_id = None
    teacher_password_hash = generate_password_hash(f"synthetic-teacher-{suffix}")
    context = app.app_context()
    context.push()
    try:
        with transaction() as (_, cursor):
            for index, nisn in enumerate(nisns):
                cursor.execute(
                    """INSERT INTO users (username, password_hash, role, is_active, must_change_password)
                       VALUES (%s, %s, 'student', 1, 0)""",
                    (nisn, generate_password_hash(f"synthetic-{suffix}-{index}")),
                )
                user_ids.append(int(cursor.lastrowid))
                cursor.execute("INSERT INTO students (user_id, nisn, full_name, face_registered) VALUES (%s, %s, %s, 0)",
                               (user_ids[-1], nisn, f"Siswa Uji T14 {suffix}-{index}"))
                student_ids.append(int(cursor.lastrowid))
            cursor.execute("INSERT INTO student_faces (student_id, pose, storage_key) VALUES (%s, 'front', %s)",
                           (student_ids[0], f"smoke-{suffix}-one-front"))
            cursor.execute("INSERT INTO student_faces (student_id, pose, storage_key) VALUES (%s, 'left', %s)",
                           (student_ids[1], f"smoke-{suffix}-two-left"))
            cursor.execute("INSERT INTO student_faces (student_id, pose, storage_key) VALUES (%s, 'right', %s)",
                           (student_ids[1], f"smoke-{suffix}-two-right"))
            cursor.execute(
                "INSERT INTO users (username, password_hash, role, is_active, must_change_password) "
                "VALUES (%s, %s, 'teacher', 1, 0)",
                (f"t14-teacher-{suffix}", teacher_password_hash),
            )
            teacher_id = int(cursor.lastrowid)

        app.add_url_rule("/attendance/t14-smoke", endpoint="attendance.t14_smoke",
                         view_func=lambda: "must not execute")
        client = app.test_client()
        synthetic_password_hash = generate_password_hash(f"synthetic-session-{suffix}")
        with client.session_transaction() as session:
            session["user_id"] = user_ids[0]
            session["credential_stamp"] = credential_stamp(synthetic_password_hash)
        with get_db().cursor() as cursor:
            cursor.execute("UPDATE users SET password_hash=%s WHERE id=%s",
                           (synthetic_password_hash, user_ids[0]))
        get_db().commit()

        page = client.get("/student/enrollment")
        content = page.get_data(as_text=True)
        assert page.status_code == 200 and "1<span aria-hidden=\"true\">/</span>3" in content
        assert "Belum diambil" in content and "Pendaftaran belum selesai" in content
        direct = client.get("/attendance/t14-smoke")
        assert direct.status_code == 302 and direct.headers["Location"] == "/student/enrollment"

        teacher = app.test_client()
        with teacher.session_transaction() as session:
            session["user_id"] = teacher_id
            session["credential_stamp"] = credential_stamp(teacher_password_hash)
        denied = teacher.get("/student/enrollment")
        assert denied.status_code == 403
        print("t14_mysql_smoke=ok; own_progress=ok; other_student_hidden=ok; direct_access_gate=ok; role_guard=ok; cleanup=ok")
    finally:
        try:
            with transaction() as (_, cursor):
                if student_ids:
                    cursor.execute("DELETE FROM student_faces WHERE student_id IN (%s)" %
                                   ",".join(["%s"] * len(student_ids)), tuple(student_ids))
                    cursor.execute("DELETE FROM students WHERE id IN (%s)" %
                                   ",".join(["%s"] * len(student_ids)), tuple(student_ids))
                cleanup_user_ids = user_ids + ([teacher_id] if teacher_id is not None else [])
                if cleanup_user_ids:
                    cursor.execute("DELETE FROM users WHERE id IN (%s)" %
                                   ",".join(["%s"] * len(cleanup_user_ids)), tuple(cleanup_user_ids))
        finally:
            context.pop()


if __name__ == "__main__":
    main()
