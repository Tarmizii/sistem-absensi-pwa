"""Exercise Student CRUD/account actions against local MySQL with cleanup."""

import secrets
from unittest.mock import patch

from pymysql import MySQLError
from werkzeug.security import check_password_hash

from app import create_app
from app.database import get_db, transaction
from app.services.student_service import (
    StudentConflictError, StudentValidationError, create_student,
    deactivate_student, get_student, list_students, reset_student_password,
    update_student,
)


def main():
    app = create_app({"TESTING": True})
    if app.config["APP_ENV"] == "production":
        raise SystemExit("Smoke test hanya untuk database development/test.")
    nisn = "0" + str(900000000 + secrets.randbelow(99999999))
    duplicate_nisn = "0" + str(800000000 + secrets.randbelow(99999999))
    user_id = student_id = duplicate_user_id = duplicate_student_id = None
    context = app.app_context()
    context.push()
    try:
        with get_db().cursor() as cursor:
            cursor.execute("SELECT id FROM users WHERE role='admin' AND is_active=1 ORDER BY id LIMIT 1")
            actor = cursor.fetchone()
            if actor is None:
                raise SystemExit("Akun Admin aktif belum tersedia.")
            actor_id = actor["id"]
        result = create_student(actor_user_id=actor_id, nisn=nisn, full_name="Siswa Sintetis")
        user_id, student_id = result["user_id"], result["student_id"]
        with get_db().cursor() as cursor:
            cursor.execute("SELECT role,is_active,must_change_password,password_hash FROM users WHERE id=%s", (user_id,))
            account = cursor.fetchone()
            assert account["role"] == "student" and account["is_active"] == 1 and account["must_change_password"] == 1
            assert check_password_hash(account["password_hash"], result["temporary_password"])
            cursor.execute("SELECT nisn,face_registered FROM students WHERE id=%s", (student_id,))
            profile = cursor.fetchone()
            assert profile["nisn"] == nisn and profile["face_registered"] == 0
        assert len(list_students(nisn)) == 1
        updated_nisn = "0" + nisn[1:-1] + ("1" if nisn[-1] != "1" else "2")
        update_student(actor_user_id=actor_id, student_id=student_id,
                       nisn=updated_nisn, full_name="Siswa Sintetis Diperbarui")
        assert get_student(student_id)["nisn"] == updated_nisn
        with get_db().cursor() as cursor:
            cursor.execute("SELECT username FROM users WHERE id=%s", (user_id,))
            assert cursor.fetchone()["username"] == updated_nisn
        try:
            create_student(actor_user_id=actor_id, nisn=updated_nisn, full_name="Duplikat")
        except StudentConflictError:
            pass
        else:
            raise AssertionError("duplicate NISN tidak ditolak")
        duplicate = create_student(actor_user_id=actor_id, nisn=duplicate_nisn, full_name="Rollback Siswa")
        duplicate_user_id, duplicate_student_id = duplicate["user_id"], duplicate["student_id"]
        with patch("app.services.student_service.record_audit", side_effect=MySQLError("synthetic audit failure")):
            try:
                update_student(actor_user_id=actor_id, student_id=duplicate_student_id,
                               nisn=duplicate_nisn, full_name="Seharusnya Rollback")
            except MySQLError:
                pass
            else:
                raise AssertionError("audit failure tidak menggagalkan update")
        assert get_student(duplicate_student_id)["full_name"] == "Rollback Siswa"
        reset = reset_student_password(actor_user_id=actor_id, student_id=student_id)
        with get_db().cursor() as cursor:
            cursor.execute("SELECT password_hash,must_change_password FROM users WHERE id=%s", (user_id,))
            account = cursor.fetchone()
            assert account["must_change_password"] == 1 and check_password_hash(account["password_hash"], reset["temporary_password"])
        deactivate_student(actor_user_id=actor_id, student_id=student_id)
        assert get_student(student_id)["is_active"] == 0 and get_student(student_id)["face_registered"] == 0
        try:
            reset_student_password(actor_user_id=actor_id, student_id=student_id)
        except StudentValidationError:
            pass
        else:
            raise AssertionError("reset akun nonaktif tidak ditolak")
        with get_db().cursor() as cursor:
            cursor.execute("SELECT action,metadata FROM audit_logs WHERE target_type='student' AND target_id=%s ORDER BY id", (student_id,))
            logs = cursor.fetchall()
            assert {row["action"] for row in logs} == {"student_created", "student_updated", "student_password_reset", "student_deactivated"}
            assert all(result["temporary_password"] not in row["metadata"] for row in logs)
        print("t09_mysql_smoke=ok; atomic_crud=ok; nisn_sync=ok; duplicate=ok; reset=ok; deactivate=ok; cleanup=ok")
    finally:
        with transaction() as (_, cursor):
            if student_id is not None:
                cursor.execute("DELETE FROM audit_logs WHERE target_type='student' AND target_id=%s", (student_id,))
                cursor.execute("DELETE FROM students WHERE id=%s", (student_id,))
            if duplicate_user_id is not None:
                cursor.execute("DELETE FROM audit_logs WHERE target_type='student' AND target_id=%s", (duplicate_student_id,))
                cursor.execute("DELETE FROM students WHERE user_id=%s", (duplicate_user_id,))
                cursor.execute("DELETE FROM users WHERE id=%s", (duplicate_user_id,))
            if user_id is not None:
                cursor.execute("DELETE FROM users WHERE id=%s", (user_id,))
        context.pop()


if __name__ == "__main__":
    main()
