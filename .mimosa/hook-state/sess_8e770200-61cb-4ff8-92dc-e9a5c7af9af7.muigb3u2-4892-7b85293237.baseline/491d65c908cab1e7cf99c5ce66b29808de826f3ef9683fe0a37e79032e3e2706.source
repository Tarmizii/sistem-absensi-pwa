"""Exercise regular schedule persistence and server-time boundaries locally."""

from datetime import date, datetime
import secrets
from unittest.mock import patch

from pymysql import MySQLError

from app import create_app
from app.database import get_db, transaction
from app.services.class_service import create_academic_year
from app.services.schedule_service import (
    ScheduleConflictError,
    create_schedule,
    can_checkout,
    evaluate_checkin,
    get_schedule,
    resolve_schedule,
    set_schedule_active,
    update_schedule,
)


def main():
    app = create_app({"TESTING": True})
    if app.config["APP_ENV"] == "production":
        raise SystemExit("Smoke test hanya untuk database development/test.")
    suffix = secrets.token_hex(6)
    year_id = schedule_id = None
    context = app.app_context()
    context.push()
    try:
        with get_db().cursor() as cursor:
            cursor.execute("SELECT id FROM users WHERE role='admin' AND is_active=1 ORDER BY id LIMIT 1")
            actor = cursor.fetchone()
            if actor is None:
                raise SystemExit("Akun Admin aktif belum tersedia.")
            actor_id = actor["id"]
        year = create_academic_year(actor_user_id=actor_id, name=f"{2020 + int(suffix[:2], 16) % 50:04d}/{2021 + int(suffix[:2], 16) % 50:04d}",
                                    start_date="2026-07-01", end_date="2027-06-30", is_active=True)
        year_id = year["id"]
        schedule = create_schedule(actor_user_id=actor_id, academic_year_id=year_id, day_of_week=5,
                                   checkin_start="07:00", late_after="07:15", checkin_cutoff="08:00",
                                   checkout_start="15:00", is_active=True)
        schedule_id = schedule["schedule_id"]
        resolved = resolve_schedule(date(2026, 9, 25), year_id)
        assert resolved["schedule_id"] == schedule_id and resolved["checkin_start"] == "07:00"
        assert evaluate_checkin(resolved, datetime(2026, 9, 25, 7, 0))["status"] == "present"
        assert evaluate_checkin(resolved, datetime(2026, 9, 25, 7, 15))["status"] == "late"
        assert evaluate_checkin(resolved, datetime(2026, 9, 25, 8, 1))["allowed"] is False
        assert can_checkout(resolved, datetime(2026, 9, 25, 14, 59)) is False
        assert can_checkout(resolved, datetime(2026, 9, 25, 15, 0)) is True
        try:
            create_schedule(actor_user_id=actor_id, academic_year_id=year_id, day_of_week=5,
                            checkin_start="07:00", late_after="07:15", checkin_cutoff="08:00",
                            checkout_start="15:00")
        except ScheduleConflictError:
            pass
        else:
            raise AssertionError("jadwal ganda tidak ditolak")
        with patch("app.services.schedule_service.record_audit", side_effect=MySQLError("synthetic audit failure")):
            try:
                update_schedule(actor_user_id=actor_id, schedule_id=schedule_id, day_of_week=5,
                                checkin_start="07:05", late_after="07:20", checkin_cutoff="08:05",
                                checkout_start="15:05")
            except MySQLError:
                pass
            else:
                raise AssertionError("audit failure tidak menggagalkan update jadwal")
        assert get_schedule(schedule_id)["checkin_start"] == "07:00"
        set_schedule_active(actor_user_id=actor_id, schedule_id=schedule_id, is_active=False)
        assert resolve_schedule(date(2026, 9, 25), year_id) is None
        set_schedule_active(actor_user_id=actor_id, schedule_id=schedule_id, is_active=True)
        assert resolve_schedule(date(2026, 9, 25), year_id)["schedule_id"] == schedule_id
        with get_db().cursor() as cursor:
            cursor.execute("SELECT action, metadata FROM audit_logs WHERE target_type='schedule' AND target_id=%s ORDER BY id", (schedule_id,))
            logs = cursor.fetchall()
            assert {row["action"] for row in logs} == {"schedule_created", "schedule_deactivated", "schedule_activated"}
        print("t11_mysql_smoke=ok; schedule_crud=ok; boundary=ok; duplicate=ok; rollback=ok; toggle=ok; resolver=ok; cleanup=ok")
    finally:
        with transaction() as (_, cursor):
            if schedule_id is not None:
                cursor.execute("DELETE FROM audit_logs WHERE target_type='schedule' AND target_id=%s", (schedule_id,))
                cursor.execute("DELETE FROM attendance_schedules WHERE id=%s", (schedule_id,))
            if year_id is not None:
                cursor.execute("DELETE FROM audit_logs WHERE target_type='academic_year' AND target_id=%s", (year_id,))
                cursor.execute("DELETE FROM academic_years WHERE id=%s", (year_id,))
        context.pop()


if __name__ == "__main__":
    main()
