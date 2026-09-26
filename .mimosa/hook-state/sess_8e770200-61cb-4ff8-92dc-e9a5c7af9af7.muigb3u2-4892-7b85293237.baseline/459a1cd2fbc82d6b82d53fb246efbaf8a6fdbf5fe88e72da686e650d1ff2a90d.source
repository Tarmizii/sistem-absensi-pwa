"""Exercise academic-year, class, teacher-scope, and placement rules locally."""

import secrets
from unittest.mock import patch

from pymysql import MySQLError

from app import create_app
from app.database import get_db, transaction
from app.services.class_service import (
    MasterDataConflictError,
    assign_student,
    create_academic_year,
    create_class,
    deactivate_class,
    list_class_students,
    list_teacher_classes,
    set_academic_year_active,
)
from app.services.student_service import create_student
from app.services.teacher_service import create_teacher


def main():
    app = create_app({"TESTING": True})
    if app.config["APP_ENV"] == "production":
        raise SystemExit("Smoke test hanya untuk database development/test.")
    suffix = secrets.token_hex(6)
    year_id = class_id = teacher_user_id = teacher_id = student_user_id = student_id = enrollment_id = None
    context = app.app_context()
    context.push()
    try:
        with get_db().cursor() as cursor:
            cursor.execute("SELECT id FROM users WHERE role='admin' AND is_active=1 ORDER BY id LIMIT 1")
            actor = cursor.fetchone()
            if actor is None:
                raise SystemExit("Akun Admin aktif belum tersedia.")
            actor_id = actor["id"]
        teacher = create_teacher(actor_user_id=actor_id, username=f"t10.teacher.{suffix}",
                                 full_name="Guru T10", employee_number=f"T10{suffix}")
        teacher_user_id, teacher_id = teacher["user_id"], teacher["teacher_id"]
        student = create_student(actor_user_id=actor_id, nisn="7" + str(100000000 + secrets.randbelow(89999999)),
                                 full_name="Siswa T10")
        student_user_id, student_id = student["user_id"], student["student_id"]
        year_start = 2020 + int(suffix[:2], 16) % 50
        year = create_academic_year(actor_user_id=actor_id, name=f"{year_start:04d}/{year_start + 1:04d}",
                                    start_date="2026-07-01", end_date="2027-06-30", is_active=True)
        year_id = year["id"]
        second_year = create_academic_year(actor_user_id=actor_id, name=f"{year_start - 1:04d}/{year_start:04d}",
                                           start_date="2025-07-01", end_date="2026-06-30", is_active=False)
        second_year_id = second_year["id"]
        class_row = create_class(actor_user_id=actor_id, name="X T10", academic_year_id=year_id, teacher_id=teacher_id)
        class_id = class_row["class_id"]
        placement = assign_student(actor_user_id=actor_id, class_id=class_id, student_id=student_id)
        enrollment_id = placement["enrollment_id"]
        assert len(list_class_students(class_id)) == 1
        assert len(list_teacher_classes(teacher_user_id)) == 1
        try:
            assign_student(actor_user_id=actor_id, class_id=class_id, student_id=student_id)
        except MasterDataConflictError:
            pass
        else:
            raise AssertionError("penempatan ganda dalam tahun ajaran tidak ditolak")
        with patch("app.services.class_service.record_audit", side_effect=MySQLError("synthetic audit failure")):
            try:
                set_academic_year_active(actor_user_id=actor_id, academic_year_id=second_year_id, is_active=True)
            except MySQLError:
                pass
            else:
                raise AssertionError("kegagalan audit tidak menggagalkan aktivasi tahun")
        with get_db().cursor() as cursor:
            cursor.execute("SELECT is_active FROM academic_years WHERE id=%s", (year_id,))
            assert cursor.fetchone()["is_active"] == 1
        deactivate_class(actor_user_id=actor_id, class_id=class_id)
        assert list_class_students(class_id)[0]["student_id"] == student_id
        print("t10_mysql_smoke=ok; academic_year=ok; class_crud=ok; teacher_scope=ok; duplicate_placement=ok; rollback=ok; history=ok; cleanup=ok")
    finally:
        with transaction() as (_, cursor):
            if enrollment_id is not None:
                cursor.execute("DELETE FROM audit_logs WHERE target_type='student_enrollment' AND target_id=%s", (enrollment_id,))
                cursor.execute("DELETE FROM student_class_enrollments WHERE id=%s", (enrollment_id,))
            if class_id is not None:
                cursor.execute("DELETE FROM audit_logs WHERE target_type='class' AND target_id=%s", (class_id,))
                cursor.execute("DELETE FROM classes WHERE id=%s", (class_id,))
            if year_id is not None:
                cursor.execute("DELETE FROM audit_logs WHERE target_type='academic_year' AND target_id=%s", (year_id,))
                cursor.execute("DELETE FROM academic_years WHERE id=%s", (year_id,))
            if 'second_year_id' in locals():
                cursor.execute("DELETE FROM audit_logs WHERE target_type='academic_year' AND target_id=%s", (second_year_id,))
                cursor.execute("DELETE FROM academic_years WHERE id=%s", (second_year_id,))
            if teacher_id is not None:
                cursor.execute("DELETE FROM audit_logs WHERE target_type='teacher' AND target_id=%s", (teacher_id,))
                cursor.execute("DELETE FROM teachers WHERE id=%s", (teacher_id,))
            if teacher_user_id is not None:
                cursor.execute("DELETE FROM users WHERE id=%s", (teacher_user_id,))
            if student_id is not None:
                cursor.execute("DELETE FROM audit_logs WHERE target_type='student' AND target_id=%s", (student_id,))
                cursor.execute("DELETE FROM students WHERE id=%s", (student_id,))
            if student_user_id is not None:
                cursor.execute("DELETE FROM users WHERE id=%s", (student_user_id,))
        context.pop()


if __name__ == "__main__":
    main()
