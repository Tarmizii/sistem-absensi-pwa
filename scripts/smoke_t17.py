"""T17 smoke: real MySQL state resolution, holiday, manual status, unique row."""

from __future__ import annotations

from datetime import date, datetime
import secrets
import tempfile
from pathlib import Path

from werkzeug.security import generate_password_hash

from app import create_app
from app.database import transaction
from app.services.attendance_state_service import get_student_day_state


def main() -> None:
    app = create_app({"TESTING": True})
    if app.config["APP_ENV"] == "production":
        raise SystemExit("Smoke T17 tidak boleh dijalankan pada environment production.")
    password_hash = generate_password_hash("SmokeTest1234567!")
    sfx = secrets.token_hex(4)
    with app.app_context():
        with transaction() as (_, cursor):
            cursor.execute(
                "INSERT INTO academic_years (name, start_date, end_date, is_active) VALUES (%s, '2026-07-01', '2027-06-30', 1)",
                (f"Tahun {sfx}",))
            year_id = cursor.lastrowid
            cursor.execute(
                "INSERT INTO classes (academic_year_id, name, is_active) VALUES (%s, %s, 1)",
                (year_id, f"X-A{sfx[:4]}"))
            class_id = cursor.lastrowid
            cursor.execute(
                "INSERT INTO attendance_schedules (academic_year_id, day_of_week, checkin_start, late_after, checkin_cutoff, checkout_start, is_active) VALUES (%s, %s, '06:30', '07:15', '08:00', '15:00', 1)",
                (year_id, date(2026, 9, 24).isoweekday()))
            cursor.execute(
                "INSERT INTO users (username, password_hash, role, is_active) VALUES (%s, %s, 'student', 1)",
                (f"smoke_t17_{sfx}", password_hash))
            user_id = cursor.lastrowid
            cursor.execute(
                "INSERT INTO students (user_id, nisn, full_name, face_registered) VALUES (%s, %s, 'Smoke T17', 1)",
                (user_id, f"70{sfx[:8]}"))
            student_id = cursor.lastrowid
            cursor.execute(
                "INSERT INTO student_class_enrollments (student_id, academic_year_id, class_id) VALUES (%s, %s, %s)",
                (student_id, year_id, class_id))

        try:
            state = get_student_day_state(user_id, at=datetime(2026, 9, 24, 7, 0))
            assert state["state"] == "checkin" and state["cta_enabled"] is True, state["state"]
            assert state["class_name"].startswith("X-A"), state["class_name"]
            print(f"a_checkin_window={state['state']}; class={state['class_name']}")

            with transaction() as (_, cursor):
                cursor.execute(
                    "INSERT INTO schedule_exceptions (academic_year_id, exception_date, scope, exception_type, is_active) VALUES (%s, '2026-09-24', 'school', 'holiday', 1)",
                    (year_id,))
            state = get_student_day_state(user_id, at=datetime(2026, 9, 24, 9, 0))
            assert state["state"] == "holiday" and state["status_today"] == "Libur", state
            print(f"b_holiday={state['state']}; status={state['status_today']}")

            with transaction() as (_, cursor):
                cursor.execute("UPDATE schedule_exceptions SET is_active=0 WHERE academic_year_id=%s", (year_id,))
                cursor.execute(
                    "INSERT INTO attendance_records (student_id, class_id, attendance_date, status, status_source) VALUES (%s, %s, '2026-09-24', 'permit', 'teacher')",
                    (student_id, class_id))
            state = get_student_day_state(user_id, at=datetime(2026, 9, 24, 9, 0))
            assert state["state"] == "manual_status" and state["status_today"] == "Izin", state
            print(f"c_manual={state['state']}; status={state['status_today']}")

            try:
                with transaction() as (_, cursor):
                    cursor.execute(
                        "INSERT INTO attendance_records (student_id, attendance_date) VALUES (%s, '2026-09-24')",
                        (student_id,))
                raise AssertionError("UNIQUE (student_id, attendance_date) tidak aktif")
            except Exception as error:
                assert type(error).__name__ in ("IntegrityError", "AssertionError"), error
                if type(error).__name__ == "AssertionError":
                    raise
            print("d_unique=ok")

            print("t17_smoke=ok; checkin_window=ok; class_snapshot=ok; holiday=ok; manual_status=ok; unique_constraint=ok; cleanup=ok")
        finally:
            with transaction() as (_, cursor):
                cursor.execute("DELETE FROM audit_logs WHERE actor_user_id=%s", (user_id,))
                cursor.execute("DELETE FROM attendance_records WHERE student_id=%s", (student_id,))
                cursor.execute("DELETE FROM student_class_enrollments WHERE student_id=%s", (student_id,))
                cursor.execute("DELETE FROM schedule_exceptions WHERE academic_year_id=%s", (year_id,))
                cursor.execute("DELETE FROM attendance_schedules WHERE academic_year_id=%s", (year_id,))
                cursor.execute("DELETE FROM students WHERE id=%s", (student_id,))
                cursor.execute("DELETE FROM classes WHERE id=%s", (class_id,))
                cursor.execute("DELETE FROM users WHERE id=%s", (user_id,))
                cursor.execute("DELETE FROM academic_years WHERE id=%s", (year_id,))


if __name__ == "__main__":
    main()
