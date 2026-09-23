"""Exercise T12 exception CRUD, precedence, audit, and rollback in dev MySQL."""

from datetime import date, time
import secrets
from unittest.mock import patch

from pymysql import MySQLError

from app import create_app
from app.database import get_db, transaction
from app.services.class_service import create_academic_year, create_class
from app.services.schedule_exception_service import (
    ScheduleExceptionError,
    create_schedule_exception,
    resolve_effective_schedule,
    set_schedule_exception_active,
    update_schedule_exception,
)
from app.services.schedule_service import can_checkout, create_schedule, evaluate_checkin


def main():
    app = create_app({"TESTING": True})
    if app.config["APP_ENV"] == "production":
        raise SystemExit("Smoke test hanya untuk database development/test.")
    suffix = secrets.token_hex(3)
    start_year = 2000 + int(suffix[:2], 16)
    year_id = schedule_id = None
    class_ids = []
    exception_ids = []
    context = app.app_context()
    context.push()
    try:
        with get_db().cursor() as cursor:
            cursor.execute("SELECT id FROM users WHERE role='admin' AND is_active=1 ORDER BY id LIMIT 1")
            actor = cursor.fetchone()
            if actor is None:
                raise SystemExit("Akun Admin aktif belum tersedia.")
        actor_id = int(actor["id"])
        year = create_academic_year(
            actor_user_id=actor_id, name=f"{start_year}/{start_year + 1}",
            start_date=f"{start_year}-01-01", end_date=f"{start_year + 1}-12-31",
            is_active=False,
        )
        year_id = int(year["id"])
        class_a = create_class(actor_user_id=actor_id, academic_year_id=year_id,
                               name=f"Uji T12 A {suffix}")
        class_ids.append(int(class_a["class_id"]))
        class_b = create_class(actor_user_id=actor_id, academic_year_id=year_id,
                               name=f"Uji T12 B {suffix}")
        class_ids.append(int(class_b["class_id"]))
        school_day = date(start_year, 9, 25)
        day_of_week = school_day.isoweekday()
        schedule = create_schedule(actor_user_id=actor_id, academic_year_id=year_id,
                                   day_of_week=day_of_week, checkin_start="07:00",
                                   late_after="07:15", checkin_cutoff="08:00",
                                   checkout_start="15:00", is_active=True)
        schedule_id = int(schedule["schedule_id"])

        school_exception = create_schedule_exception(
            actor_user_id=actor_id, academic_year_id=year_id, exception_date=school_day,
            scope="school", class_id=None, exception_type="exam",
            checkin_start="07:05", late_after="07:20",
        )
        exception_ids.append(school_exception)
        class_exception = create_schedule_exception(
            actor_user_id=actor_id, academic_year_id=year_id, exception_date=school_day,
            scope="class", class_id=class_ids[0], exception_type="early_dismissal",
            checkin_start="07:10", checkout_start="14:00",
        )
        exception_ids.append(class_exception)
        class_preview = resolve_effective_schedule(school_day, year_id, class_ids[0])
        other_preview = resolve_effective_schedule(school_day, year_id, class_ids[1])
        assert class_preview["source"] == "class"
        assert class_preview["checkin_start"] == "07:10"
        assert class_preview["late_after"] == "07:20" and class_preview["checkout_start"] == "14:00"
        assert other_preview["source"] == "school" and other_preview["checkin_start"] == "07:05"
        assert other_preview["checkout_start"] == "15:00"
        assert evaluate_checkin(class_preview, time(7, 20))["status"] == "late"
        assert can_checkout(class_preview, time(14))

        try:
            create_schedule_exception(
                actor_user_id=actor_id, academic_year_id=year_id, exception_date=school_day,
                scope="school", class_id=None, exception_type="exam", late_after="07:25",
            )
        except ScheduleExceptionError:
            pass
        else:
            raise AssertionError("exception duplikat pada scope/tanggal diterima")

        update_schedule_exception(
            actor_user_id=actor_id, exception_id=school_exception, academic_year_id=year_id,
            exception_date=school_day, scope="school", class_id=None, exception_type="exam",
            late_after="07:25",
        )
        assert resolve_effective_schedule(school_day, year_id, class_ids[1])["late_after"] == "07:25"
        set_schedule_exception_active(actor_user_id=actor_id, exception_id=school_exception,
                                     is_active=False)
        assert resolve_effective_schedule(school_day, year_id, class_ids[1])["late_after"] == "07:15"
        set_schedule_exception_active(actor_user_id=actor_id, exception_id=school_exception,
                                     is_active=True)

        holiday_day = date.fromordinal(school_day.toordinal() + 1)
        holiday = create_schedule_exception(
            actor_user_id=actor_id, academic_year_id=year_id, exception_date=holiday_day,
            scope="school", class_id=None, exception_type="holiday",
        )
        exception_ids.append(holiday)
        holiday_preview = resolve_effective_schedule(holiday_day, year_id)
        assert holiday_preview is not None and holiday_preview["is_holiday"]
        assert evaluate_checkin(holiday_preview, "07:00")["state"] == "holiday"
        assert can_checkout(holiday_preview, "15:00") is False

        rollback_day = date.fromordinal(holiday_day.toordinal() + 1)
        try:
            with patch("app.services.schedule_exception_service.record_audit",
                       side_effect=MySQLError("synthetic audit failure")):
                create_schedule_exception(
                    actor_user_id=actor_id, academic_year_id=year_id, exception_date=rollback_day,
                    scope="school", class_id=None, exception_type="holiday",
                )
        except MySQLError:
            pass
        else:
            raise AssertionError("kegagalan audit tidak menggagalkan simpan exception")
        with get_db().cursor() as cursor:
            cursor.execute("SELECT id FROM schedule_exceptions WHERE academic_year_id=%s AND exception_date=%s",
                           (year_id, rollback_day))
            assert cursor.fetchone() is None
            cursor.execute("SELECT action FROM audit_logs WHERE target_type='schedule_exception' AND target_id=%s",
                           (school_exception,))
            school_actions = {row["action"] for row in cursor.fetchall()}
            assert {"schedule_exception_created", "schedule_exception_updated",
                    "schedule_exception_deactivated", "schedule_exception_activated"} <= school_actions
        print("t12_mysql_smoke=ok; scope_precedence=ok; inherited_fields=ok; duplicate=ok; holiday=ok; audit_rollback=ok; cleanup=ok")
    finally:
        with transaction() as (_, cursor):
            for exception_id in exception_ids:
                cursor.execute("DELETE FROM audit_logs WHERE target_type='schedule_exception' AND target_id=%s",
                               (exception_id,))
            if exception_ids:
                cursor.execute("DELETE FROM schedule_exceptions WHERE id IN (%s)" %
                               ",".join(["%s"] * len(exception_ids)), tuple(exception_ids))
            if schedule_id is not None:
                cursor.execute("DELETE FROM audit_logs WHERE target_type='schedule' AND target_id=%s", (schedule_id,))
                cursor.execute("DELETE FROM attendance_schedules WHERE id=%s", (schedule_id,))
            for class_id in class_ids:
                cursor.execute("DELETE FROM audit_logs WHERE target_type='class' AND target_id=%s", (class_id,))
                cursor.execute("DELETE FROM classes WHERE id=%s", (class_id,))
            if year_id is not None:
                cursor.execute("DELETE FROM audit_logs WHERE target_type='academic_year' AND target_id=%s", (year_id,))
                cursor.execute("DELETE FROM academic_years WHERE id=%s", (year_id,))
        context.pop()


if __name__ == "__main__":
    main()
