"""Exercise Teacher CRUD/account actions against local MySQL with cleanup."""

import secrets
from unittest.mock import patch

from pymysql import MySQLError
from werkzeug.security import check_password_hash

from app import create_app
from app.database import get_db, transaction
from app.services.teacher_service import (
    TeacherConflictError, TeacherValidationError, create_teacher,
    deactivate_teacher, get_teacher, list_teachers, reset_teacher_password,
    update_teacher,
)


def main():
    app = create_app({"TESTING": True})
    if app.config["APP_ENV"] == "production":
        raise SystemExit("Smoke test hanya untuk database development/test.")
    username = "__t08_" + secrets.token_hex(8)
    duplicate_username = "__t08_duplicate_" + secrets.token_hex(6)
    employee_number = "T08" + secrets.token_hex(5)
    user_id = teacher_id = duplicate_user_id = duplicate_teacher_id = None
    context = app.app_context()
    context.push()
    try:
        with get_db().cursor() as cursor:
            cursor.execute("SELECT id FROM users WHERE role='admin' AND is_active=1 ORDER BY id LIMIT 1")
            actor = cursor.fetchone()
            if actor is None:
                raise SystemExit("Akun Admin aktif belum tersedia.")
            actor_id = actor["id"]
        result = create_teacher(actor_user_id=actor_id, username=username,
                                full_name="Guru Sintetis", employee_number=employee_number)
        user_id, teacher_id = result["user_id"], result["teacher_id"]
        with get_db().cursor() as cursor:
            cursor.execute("SELECT role,is_active,must_change_password,password_hash FROM users WHERE id=%s", (user_id,))
            account = cursor.fetchone()
            assert account["role"] == "teacher" and account["is_active"] == 1 and account["must_change_password"] == 1
            assert check_password_hash(account["password_hash"], result["temporary_password"])
        assert len(list_teachers(username)) == 1
        update_teacher(actor_user_id=actor_id, teacher_id=teacher_id,
                       full_name="Guru Sintetis Diperbarui", employee_number=employee_number)
        assert get_teacher(teacher_id)["full_name"] == "Guru Sintetis Diperbarui"
        reset = reset_teacher_password(actor_user_id=actor_id, teacher_id=teacher_id)
        with get_db().cursor() as cursor:
            cursor.execute("SELECT password_hash,must_change_password FROM users WHERE id=%s", (user_id,))
            account = cursor.fetchone()
            assert account["must_change_password"] == 1 and check_password_hash(account["password_hash"], reset["temporary_password"])
        try:
            create_teacher(actor_user_id=actor_id, username=username,
                           full_name="Duplikat", employee_number="DUP" + secrets.token_hex(3))
        except TeacherConflictError:
            pass
        else:
            raise AssertionError("duplicate username tidak ditolak")
        duplicate = create_teacher(actor_user_id=actor_id, username=duplicate_username,
                                   full_name="Rollback Guru", employee_number="RB" + secrets.token_hex(3))
        duplicate_user_id, duplicate_teacher_id = duplicate["user_id"], duplicate["teacher_id"]
        with patch("app.services.teacher_service.record_audit", side_effect=MySQLError("synthetic audit failure")):
            try:
                update_teacher(actor_user_id=actor_id, teacher_id=duplicate["teacher_id"],
                               full_name="Seharusnya Rollback", employee_number=duplicate["temporary_password"][:8])
            except MySQLError:
                pass
            else:
                raise AssertionError("audit failure tidak menggagalkan update")
        assert get_teacher(duplicate["teacher_id"])["full_name"] == "Rollback Guru"
        deactivate_teacher(actor_user_id=actor_id, teacher_id=teacher_id)
        assert get_teacher(teacher_id)["is_active"] == 0
        try:
            reset_teacher_password(actor_user_id=actor_id, teacher_id=teacher_id)
        except TeacherValidationError:
            pass
        else:
            raise AssertionError("reset akun nonaktif tidak ditolak")
        with get_db().cursor() as cursor:
            cursor.execute("SELECT action,metadata FROM audit_logs WHERE target_type='teacher' AND target_id=%s ORDER BY id", (teacher_id,))
            logs = cursor.fetchall()
            assert {row["action"] for row in logs} == {"teacher_created", "teacher_updated", "teacher_password_reset", "teacher_deactivated"}
            assert all(result["temporary_password"] not in row["metadata"] for row in logs)
        print("t08_mysql_smoke=ok; atomic_crud=ok; duplicate=ok; reset=ok; deactivate=ok; cleanup=ok")
    finally:
        with transaction() as (_, cursor):
            if teacher_id is not None:
                cursor.execute("DELETE FROM audit_logs WHERE target_type='teacher' AND target_id=%s", (teacher_id,))
                cursor.execute("DELETE FROM teachers WHERE id=%s", (teacher_id,))
            if duplicate_user_id is not None:
                cursor.execute("DELETE FROM audit_logs WHERE target_type='teacher' AND target_id=%s", (duplicate_teacher_id,))
                cursor.execute("DELETE FROM teachers WHERE user_id=%s", (duplicate_user_id,))
                cursor.execute("DELETE FROM users WHERE id=%s", (duplicate_user_id,))
            if user_id is not None:
                cursor.execute("DELETE FROM users WHERE id=%s", (user_id,))
        context.pop()


if __name__ == "__main__":
    main()
