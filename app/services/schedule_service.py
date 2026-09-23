"""Regular attendance schedule rules and server-time resolution for T11."""

from __future__ import annotations

from datetime import date, datetime, time
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from flask import current_app
from pymysql import IntegrityError

from app.database import get_db, transaction
from app.services.audit_service import record_audit


class ScheduleValidationError(ValueError):
    """Schedule input or boundary rule is invalid."""


class ScheduleConflictError(ScheduleValidationError):
    """A schedule already exists for the academic year/day."""


class ScheduleNotFoundError(ScheduleValidationError):
    """The requested schedule or academic year does not exist."""


def app_timezone() -> ZoneInfo:
    name = current_app.config.get("APP_TIMEZONE", "Asia/Jakarta")
    try:
        return ZoneInfo(name)
    except ZoneInfoNotFoundError:
        raise ScheduleValidationError("Timezone aplikasi tidak tersedia.") from None


def application_now() -> datetime:
    return datetime.now(app_timezone())


def _positive_id(value: Any, label: str) -> int:
    if type(value) is not int or value <= 0:
        raise ScheduleValidationError(f"{label} tidak valid.")
    return value


def _parse_time(value: str, label: str) -> time:
    if not isinstance(value, str):
        raise ScheduleValidationError(f"{label} harus berupa waktu HH:MM.")
    try:
        return time.fromisoformat(value.strip())
    except ValueError:
        raise ScheduleValidationError(f"{label} harus memakai format HH:MM.") from None


def _time_text(value: time | str) -> str:
    if isinstance(value, time):
        return value.strftime("%H:%M")
    return value[:5]


def validate_schedule_input(*, academic_year_id: int, day_of_week: int,
                            checkin_start: str, late_after: str,
                            checkin_cutoff: str, checkout_start: str,
                            is_active: bool = True) -> tuple[int, int, time, time, time, time, bool]:
    year_id = _positive_id(academic_year_id, "Tahun ajaran")
    if type(day_of_week) is not int or not 1 <= day_of_week <= 7:
        raise ScheduleValidationError("Hari harus berupa angka ISO 1–7 (Senin–Minggu).")
    start = _parse_time(checkin_start, "Mulai check-in")
    late = _parse_time(late_after, "Batas terlambat")
    cutoff = _parse_time(checkin_cutoff, "Batas check-in")
    checkout = _parse_time(checkout_start, "Mulai check-out")
    if not start <= late <= cutoff <= checkout:
        raise ScheduleValidationError("Urutan waktu harus mulai ≤ terlambat ≤ cutoff ≤ mulai check-out.")
    if type(is_active) is not bool:
        raise ScheduleValidationError("Status aktif jadwal tidak valid.")
    return year_id, day_of_week, start, late, cutoff, checkout, is_active


def _translate_integrity(error: IntegrityError) -> ScheduleConflictError:
    if "uq_schedules_year_day" in str(error).lower() or "academic_year_id" in str(error).lower():
        return ScheduleConflictError("Jadwal untuk hari tersebut sudah tersedia pada tahun ajaran ini.")
    return ScheduleConflictError("Jadwal bertabrakan dengan data yang sudah ada.")


def list_schedules(academic_year_id: int | None = None) -> list[dict[str, Any]]:
    params: tuple[Any, ...] = ()
    where = ""
    if academic_year_id is not None:
        year_id = _positive_id(academic_year_id, "Tahun ajaran")
        where = "WHERE s.academic_year_id=%s"
        params = (year_id,)
    with get_db().cursor() as cursor:
        cursor.execute(
            f"""SELECT s.id AS schedule_id, s.academic_year_id, s.day_of_week,
                      TIME_FORMAT(s.checkin_start, '%%H:%%i') AS checkin_start,
                      TIME_FORMAT(s.late_after, '%%H:%%i') AS late_after,
                      TIME_FORMAT(s.checkin_cutoff, '%%H:%%i') AS checkin_cutoff,
                      TIME_FORMAT(s.checkout_start, '%%H:%%i') AS checkout_start,
                      s.is_active, ay.name AS academic_year_name
               FROM attendance_schedules AS s JOIN academic_years AS ay
                 ON ay.id=s.academic_year_id {where}
               ORDER BY ay.start_date DESC, s.day_of_week, s.id LIMIT 200""", params
        )
        return list(cursor.fetchall())


def get_schedule(schedule_id: int) -> dict[str, Any] | None:
    with get_db().cursor() as cursor:
        cursor.execute(
            """SELECT s.id AS schedule_id, s.academic_year_id, s.day_of_week,
                      TIME_FORMAT(s.checkin_start, '%%H:%%i') AS checkin_start,
                      TIME_FORMAT(s.late_after, '%%H:%%i') AS late_after,
                      TIME_FORMAT(s.checkin_cutoff, '%%H:%%i') AS checkin_cutoff,
                      TIME_FORMAT(s.checkout_start, '%%H:%%i') AS checkout_start,
                      s.is_active, ay.name AS academic_year_name
               FROM attendance_schedules AS s JOIN academic_years AS ay
                 ON ay.id=s.academic_year_id WHERE s.id=%s LIMIT 1""", (schedule_id,)
        )
        return cursor.fetchone()


def create_schedule(*, actor_user_id: int, academic_year_id: int, day_of_week: int,
                    checkin_start: str, late_after: str, checkin_cutoff: str,
                    checkout_start: str, is_active: bool = True) -> dict[str, Any]:
    year_id, day, start, late, cutoff, checkout, active = validate_schedule_input(
        academic_year_id=academic_year_id, day_of_week=day_of_week,
        checkin_start=checkin_start, late_after=late_after,
        checkin_cutoff=checkin_cutoff, checkout_start=checkout_start,
        is_active=is_active,
    )
    try:
        with transaction() as (_, cursor):
            cursor.execute("SELECT id FROM academic_years WHERE id=%s LIMIT 1", (year_id,))
            if cursor.fetchone() is None:
                raise ScheduleNotFoundError("Tahun ajaran tidak ditemukan.")
            cursor.execute(
                """INSERT INTO attendance_schedules
                   (academic_year_id, day_of_week, checkin_start, late_after,
                    checkin_cutoff, checkout_start, is_active)
                   VALUES (%s,%s,%s,%s,%s,%s,%s)""",
                (year_id, day, start, late, cutoff, checkout, active),
            )
            schedule_id = int(cursor.lastrowid)
            record_audit(cursor, actor_user_id=actor_user_id, action="schedule_created",
                         target_type="schedule", target_id=schedule_id,
                         metadata={"is_active": active})
    except IntegrityError as error:
        raise _translate_integrity(error) from None
    return get_schedule(schedule_id) or {"schedule_id": schedule_id, "academic_year_id": year_id,
                                         "day_of_week": day, "is_active": active}


def update_schedule(*, actor_user_id: int, schedule_id: int, day_of_week: int,
                    checkin_start: str, late_after: str, checkin_cutoff: str,
                    checkout_start: str) -> dict[str, Any]:
    _, day, start, late, cutoff, checkout, _ = validate_schedule_input(
        academic_year_id=1, day_of_week=day_of_week,
        checkin_start=checkin_start, late_after=late_after,
        checkin_cutoff=checkin_cutoff, checkout_start=checkout_start,
        is_active=True,
    )
    try:
        with transaction() as (_, cursor):
            cursor.execute("SELECT id FROM attendance_schedules WHERE id=%s FOR UPDATE", (schedule_id,))
            if cursor.fetchone() is None:
                raise ScheduleNotFoundError("Jadwal tidak ditemukan.")
            cursor.execute(
                """UPDATE attendance_schedules
                   SET day_of_week=%s, checkin_start=%s, late_after=%s,
                       checkin_cutoff=%s, checkout_start=%s WHERE id=%s""",
                (day, start, late, cutoff, checkout, schedule_id),
            )
            record_audit(cursor, actor_user_id=actor_user_id, action="schedule_updated",
                         target_type="schedule", target_id=schedule_id,
                         metadata={"fields": ["day_of_week", "checkin_start", "late_after",
                                               "checkin_cutoff", "checkout_start"]})
    except IntegrityError as error:
        raise _translate_integrity(error) from None
    return get_schedule(schedule_id) or {"schedule_id": schedule_id, "day_of_week": day}


def set_schedule_active(*, actor_user_id: int, schedule_id: int, is_active: bool) -> None:
    if type(is_active) is not bool:
        raise ScheduleValidationError("Status aktif jadwal tidak valid.")
    with transaction() as (_, cursor):
        cursor.execute("SELECT is_active FROM attendance_schedules WHERE id=%s FOR UPDATE", (schedule_id,))
        schedule = cursor.fetchone()
        if schedule is None:
            raise ScheduleNotFoundError("Jadwal tidak ditemukan.")
        cursor.execute("UPDATE attendance_schedules SET is_active=%s WHERE id=%s", (is_active, schedule_id))
        if bool(schedule["is_active"]) != is_active:
            record_audit(cursor, actor_user_id=actor_user_id,
                         action="schedule_activated" if is_active else "schedule_deactivated",
                         target_type="schedule", target_id=schedule_id,
                         metadata={"is_active": is_active})


def resolve_regular_schedule(for_date: date, academic_year_id: int | None = None) -> dict[str, Any] | None:
    if not isinstance(for_date, date) or isinstance(for_date, datetime):
        raise ScheduleValidationError("Tanggal jadwal tidak valid.")
    day = for_date.isoweekday()
    with get_db().cursor() as cursor:
        if academic_year_id is None:
            cursor.execute(
                """SELECT id FROM academic_years
                   WHERE is_active=1 AND start_date<=%s AND end_date>=%s
                   ORDER BY start_date DESC, id DESC LIMIT 1""", (for_date, for_date)
            )
            year = cursor.fetchone()
            if year is None:
                return None
            year_id = year["id"]
        else:
            year_id = _positive_id(academic_year_id, "Tahun ajaran")
        cursor.execute(
            """SELECT s.id AS schedule_id, s.academic_year_id, s.day_of_week,
                      TIME_FORMAT(s.checkin_start, '%%H:%%i') AS checkin_start,
                      TIME_FORMAT(s.late_after, '%%H:%%i') AS late_after,
                      TIME_FORMAT(s.checkin_cutoff, '%%H:%%i') AS checkin_cutoff,
                      TIME_FORMAT(s.checkout_start, '%%H:%%i') AS checkout_start,
                      s.is_active
               FROM attendance_schedules AS s JOIN academic_years AS ay
                 ON ay.id=s.academic_year_id
               WHERE s.academic_year_id=%s AND s.day_of_week=%s AND s.is_active=1
                 AND ay.start_date<=%s AND ay.end_date>=%s LIMIT 1""",
            (year_id, day, for_date, for_date),
        )
        return cursor.fetchone()


def resolve_schedule(for_date: date, academic_year_id: int | None = None,
                     class_id: int | None = None) -> dict[str, Any] | None:
    """Resolve schedule exceptions and regular fallback for attendance use."""
    from app.services.schedule_exception_service import resolve_effective_schedule

    return resolve_effective_schedule(for_date, academic_year_id, class_id)


def evaluate_checkin(schedule: dict[str, Any], at: datetime | time | None = None) -> dict[str, Any]:
    if schedule.get("is_holiday"):
        return {"allowed": False, "state": "holiday", "status": None}
    current = application_now() if at is None else at
    current_time = current.timetz().replace(tzinfo=None) if isinstance(current, datetime) else current
    start = schedule["checkin_start"] if isinstance(schedule["checkin_start"], time) else _parse_time(str(schedule["checkin_start"]), "Mulai check-in")
    late = schedule["late_after"] if isinstance(schedule["late_after"], time) else _parse_time(str(schedule["late_after"]), "Batas terlambat")
    cutoff = schedule["checkin_cutoff"] if isinstance(schedule["checkin_cutoff"], time) else _parse_time(str(schedule["checkin_cutoff"]), "Batas check-in")
    if current_time < start:
        return {"allowed": False, "state": "before_start", "status": None}
    if current_time > cutoff:
        return {"allowed": False, "state": "after_cutoff", "status": None}
    if current_time >= late:
        return {"allowed": True, "state": "late", "status": "late"}
    return {"allowed": True, "state": "on_time", "status": "present"}


def can_checkout(schedule: dict[str, Any], at: datetime | time | None = None) -> bool:
    if schedule.get("is_holiday"):
        return False
    current = application_now() if at is None else at
    current_time = current.timetz().replace(tzinfo=None) if isinstance(current, datetime) else current
    checkout = schedule["checkout_start"] if isinstance(schedule["checkout_start"], time) else _parse_time(str(schedule["checkout_start"]), "Mulai check-out")
    return current_time >= checkout
