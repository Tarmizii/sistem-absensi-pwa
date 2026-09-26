"""Exercise the student dashboard/calendar against the configured dev MySQL."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
import secrets

from werkzeug.security import generate_password_hash

from app import create_app
from app.database import get_db, transaction
from app.services.auth_service import credential_stamp
from app.services.schedule_service import application_now, database_datetime_to_local_time


def main() -> None:
    app = create_app({"TESTING": True})
    if app.config["APP_ENV"] == "production":
        raise SystemExit("Smoke T21 hanya boleh memakai database development/test.")
    suffix = secrets.token_hex(5)
    user_id = None
    student_id = None
    year_id = None
    class_id = None
    context = app.app_context()
    context.push()
    try:
        moment = application_now()
        today = moment.date()
        month = today.strftime("%Y-%m")
        password_hash = generate_password_hash(f"SyntheticT21-{suffix}-pass")
        with transaction() as (_, cursor):
            cursor.execute(
                "INSERT INTO academic_years (name, start_date, end_date, is_active) VALUES (%s,%s,%s,1)",
                (f"Smoke T21 {suffix}", date(today.year, 1, 1), date(today.year, 12, 31)),
            )
            year_id = int(cursor.lastrowid)
            cursor.execute(
                "INSERT INTO classes (academic_year_id, name, is_active) VALUES (%s,%s,1)",
                (year_id, f"X-T21-{suffix[:5]}"),
            )
            class_id = int(cursor.lastrowid)
            for weekday in range(1, 8):
                cursor.execute(
                    """INSERT INTO attendance_schedules
                       (academic_year_id, day_of_week, checkin_start, late_after,
                        checkin_cutoff, checkout_start, is_active)
                       VALUES (%s,%s,'06:30','07:15','08:00','15:00',1)""",
                    (year_id, weekday),
                )
            if today.day > 1:
                holiday = today - timedelta(days=1)
                cursor.execute(
                    """INSERT INTO schedule_exceptions
                       (academic_year_id, exception_date, scope, class_id, exception_type,
                        checkin_start, late_after, checkin_cutoff, checkout_start, is_active)
                       VALUES (%s,%s,'school',NULL,'holiday',NULL,NULL,NULL,NULL,1)""",
                    (year_id, holiday),
                )
            cursor.execute(
                "INSERT INTO users (username,password_hash,role,is_active,must_change_password) VALUES (%s,%s,'student',1,0)",
                (f"smoke-t21-{suffix}", password_hash),
            )
            user_id = int(cursor.lastrowid)
            cursor.execute(
                "INSERT INTO students (user_id,nisn,full_name,face_registered) VALUES (%s,%s,%s,1)",
                (user_id, f"92{suffix}", f"Siswa Smoke T21 {suffix}"),
            )
            student_id = int(cursor.lastrowid)
            cursor.execute(
                "INSERT INTO student_class_enrollments (student_id,academic_year_id,class_id) VALUES (%s,%s,%s)",
                (student_id, year_id, class_id),
            )
            cursor.execute(
                """INSERT INTO schedule_exceptions
                   (academic_year_id, exception_date, scope, class_id, exception_type,
                    checkin_start, late_after, checkin_cutoff, checkout_start, is_active)
                   VALUES (%s,%s,'class',%s,'holiday',NULL,NULL,NULL,NULL,1)""",
                (year_id, today, class_id),
            )
            cursor.execute(
                """INSERT INTO attendance_records
                   (student_id,class_id,attendance_date,status,status_source,notes,
                    checkin_at,checkin_photo,checkin_latitude,checkin_longitude,checkin_accuracy,
                    checkin_face_score,checkin_liveness_verified)
                   VALUES (%s,%s,%s,'present','system','catatan sintetis',%s,'private/t21.jpg',
                           5.1,97.1,8,12.3,1)""",
                (student_id, class_id, today, datetime.combine(today, time(1, 35))),
            )

        client = app.test_client()
        with client.session_transaction() as session:
            session["user_id"] = user_id
            session["credential_stamp"] = credential_stamp(password_hash)
            session["_csrf_token"] = secrets.token_urlsafe(24)

        dashboard = client.get("/student/dashboard")
        assert dashboard.status_code == 200, dashboard.get_data(as_text=True)
        assert f"Siswa Smoke T21 {suffix}" in dashboard.get_data(as_text=True)
        status = client.get("/student/attendance-state")
        assert status.status_code == 200, status.get_data(as_text=True)
        state = status.get_json()
        with get_db().cursor() as cursor:
            cursor.execute("SELECT checkin_at FROM attendance_records WHERE student_id=%s", (student_id,))
            stored_time = cursor.fetchone()["checkin_at"]
        assert state["checkin_time"] == database_datetime_to_local_time(stored_time) == "08:35", state
        assert state["status_today"] == "Hadir" and state["schedule"]["is_holiday"] is True, state
        assert state["state"] == "schedule_changed" and state["cta_enabled"] is False, state
        assert "checkin_photo" not in state and "checkin_latitude" not in status.get_data(as_text=True)
        assert client.get(f"/student/attendance-state?student_id={student_id}").status_code == 400
        assert client.get(f"/student/history?month={month}&student_id={student_id}").status_code == 400
        assert client.get("/student/history?month=2020-01").status_code == 403

        history = client.get(f"/student/history?month={month}&date={today.isoformat()}")
        assert history.status_code == 200, history.get_data(as_text=True)
        page = history.get_data(as_text=True)
        assert "Kalender presensi bulan berjalan" in page
        assert "Hadir" in page and "08:35" in page and "catatan sintetis" in page
        assert "private/t21.jpg" not in page and "97.1" not in page and "12.3" not in page
        if today.day > 1:
            assert "Libur" in page
        print("t21_mysql_smoke=ok; dashboard=ok; UTC_to_WIB=ok; current_month=ok; old_month=403; identity_override=400; private_fields=omitted")
    finally:
        try:
            with transaction() as (_, cursor):
                if student_id:
                    cursor.execute("DELETE FROM attendance_records WHERE student_id=%s", (student_id,))
                    cursor.execute("DELETE FROM student_class_enrollments WHERE student_id=%s", (student_id,))
                    cursor.execute("DELETE FROM students WHERE id=%s", (student_id,))
                if user_id:
                    cursor.execute("DELETE FROM users WHERE id=%s", (user_id,))
                if year_id:
                    cursor.execute("DELETE FROM schedule_exceptions WHERE academic_year_id=%s", (year_id,))
                    cursor.execute("DELETE FROM attendance_schedules WHERE academic_year_id=%s", (year_id,))
                if class_id:
                    cursor.execute("DELETE FROM classes WHERE id=%s", (class_id,))
                if year_id:
                    cursor.execute("DELETE FROM academic_years WHERE id=%s", (year_id,))
        finally:
            context.pop()


if __name__ == "__main__":
    main()
