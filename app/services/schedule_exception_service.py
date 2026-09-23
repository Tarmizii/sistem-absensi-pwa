"""School and class schedule exceptions with effective-date resolution."""

from __future__ import annotations

from datetime import date, datetime, time
from typing import Any

from pymysql import IntegrityError

from app.database import get_db, transaction
from app.services.audit_service import record_audit
from app.services.schedule_service import resolve_regular_schedule


EXCEPTION_TYPES = {"holiday", "exam", "school_activity", "early_dismissal", "custom"}
OVERRIDE_FIELDS = ("checkin_start", "late_after", "checkin_cutoff", "checkout_start")


class ScheduleExceptionError(ValueError):
    """Schedule exception input, conflict, or reference is invalid."""


class ScheduleExceptionNotFoundError(ScheduleExceptionError):
    """Requested schedule exception does not exist."""


def _positive_id(value: Any, label: str) -> int:
    if type(value) is not int or value <= 0:
        raise ScheduleExceptionError(f"{label} tidak valid.")
    return value


def _parse_time(value: Any, label: str) -> time | None:
    if value in (None, ""):
        return None
    if not isinstance(value, str):
        raise ScheduleExceptionError(f"{label} tidak valid.")
    try:
        parsed = time.fromisoformat(value.strip())
    except ValueError:
        raise ScheduleExceptionError(f"{label} harus memakai format HH:MM.") from None
    if parsed.second or parsed.microsecond or parsed.tzinfo:
        raise ScheduleExceptionError(f"{label} harus memakai format HH:MM.")
    return parsed


def _validate(*, academic_year_id: int, exception_date: str | date, scope: str,
              class_id: int | None, exception_type: str,
              checkin_start: str | None, late_after: str | None,
              checkin_cutoff: str | None, checkout_start: str | None
              ) -> tuple[int, date, str, int | None, str, dict[str, time | None]]:
    year_id = _positive_id(academic_year_id, "Tahun ajaran")
    if isinstance(exception_date, datetime):
        raise ScheduleExceptionError("Tanggal exception tidak valid.")
    if isinstance(exception_date, date):
        day = exception_date
    elif isinstance(exception_date, str):
        try:
            day = date.fromisoformat(exception_date.strip())
        except ValueError:
            raise ScheduleExceptionError("Tanggal harus memakai format YYYY-MM-DD.") from None
    else:
        raise ScheduleExceptionError("Tanggal exception tidak valid.")
    if not isinstance(scope, str) or scope not in {"school", "class"}:
        raise ScheduleExceptionError("Scope exception tidak valid.")
    normalized_class_id = None if class_id in (None, "", 0) else _positive_id(class_id, "Kelas")
    if (scope == "school" and normalized_class_id is not None) or (
            scope == "class" and normalized_class_id is None):
        raise ScheduleExceptionError("Kelas wajib dipilih hanya untuk scope kelas.")
    if not isinstance(exception_type, str) or exception_type not in EXCEPTION_TYPES:
        raise ScheduleExceptionError("Jenis exception tidak dikenal.")
    values = {
        "checkin_start": _parse_time(checkin_start, "Mulai check-in"),
        "late_after": _parse_time(late_after, "Mulai terlambat"),
        "checkin_cutoff": _parse_time(checkin_cutoff, "Cutoff check-in"),
        "checkout_start": _parse_time(checkout_start, "Mulai check-out"),
    }
    present = [(key, value) for key, value in values.items() if value is not None]
    if exception_type != "holiday" and not present:
        raise ScheduleExceptionError("Isi setidaknya satu waktu override untuk exception ini.")
    for (left_name, left), (right_name, right) in zip(present, present[1:]):
        if left > right:
            raise ScheduleExceptionError(f"Urutan {left_name} dan {right_name} tidak valid.")
    return year_id, day, scope, normalized_class_id, exception_type, values


def _check_references(cursor, year_id: int, day: date, scope: str,
                      class_id: int | None) -> None:
    cursor.execute("SELECT start_date, end_date FROM academic_years WHERE id=%s LIMIT 1", (year_id,))
    year = cursor.fetchone()
    if year is None:
        raise ScheduleExceptionError("Tahun ajaran tidak ditemukan.")
    if day < year["start_date"] or day > year["end_date"]:
        raise ScheduleExceptionError("Tanggal exception harus berada dalam periode tahun ajaran.")
    if scope == "class":
        cursor.execute("SELECT academic_year_id FROM classes WHERE id=%s LIMIT 1", (class_id,))
        klass = cursor.fetchone()
        if klass is None or int(klass["academic_year_id"]) != year_id:
            raise ScheduleExceptionError("Kelas tidak termasuk dalam tahun ajaran yang dipilih.")


def _translate_conflict(error: IntegrityError) -> ScheduleExceptionError:
    if "uq_schedule_exceptions_scope" in str(error).lower():
        return ScheduleExceptionError("Exception untuk tanggal dan scope tersebut sudah ada.")
    return ScheduleExceptionError("Exception bertabrakan dengan data yang sudah ada.")


def list_schedule_exceptions(academic_year_id: int | None = None) -> list[dict[str, Any]]:
    params: tuple[Any, ...] = ()
    where = ""
    if academic_year_id is not None:
        year_id = _positive_id(academic_year_id, "Tahun ajaran")
        where = "WHERE e.academic_year_id=%s"
        params = (year_id,)
    with get_db().cursor() as cursor:
        cursor.execute(
            f"""SELECT e.id AS exception_id, e.academic_year_id, ay.name AS academic_year_name,
                       e.exception_date, e.scope, e.class_id, c.name AS class_name,
                       e.exception_type,
                       TIME_FORMAT(e.checkin_start, '%%H:%%i') AS checkin_start,
                       TIME_FORMAT(e.late_after, '%%H:%%i') AS late_after,
                       TIME_FORMAT(e.checkin_cutoff, '%%H:%%i') AS checkin_cutoff,
                       TIME_FORMAT(e.checkout_start, '%%H:%%i') AS checkout_start, e.is_active
                FROM schedule_exceptions AS e
                JOIN academic_years AS ay ON ay.id=e.academic_year_id
                LEFT JOIN classes AS c ON c.id=e.class_id
                {where}
                ORDER BY e.exception_date DESC, e.scope, c.name LIMIT 300""", params
        )
        return list(cursor.fetchall())


def get_schedule_exception(exception_id: int) -> dict[str, Any] | None:
    exception_id = _positive_id(exception_id, "Exception")
    with get_db().cursor() as cursor:
        cursor.execute(
            """SELECT id AS exception_id, academic_year_id, exception_date, scope, class_id,
                      exception_type,
                      TIME_FORMAT(checkin_start, '%%H:%%i') AS checkin_start,
                      TIME_FORMAT(late_after, '%%H:%%i') AS late_after,
                      TIME_FORMAT(checkin_cutoff, '%%H:%%i') AS checkin_cutoff,
                      TIME_FORMAT(checkout_start, '%%H:%%i') AS checkout_start, is_active
               FROM schedule_exceptions WHERE id=%s LIMIT 1""", (exception_id,)
        )
        return cursor.fetchone()


def _audit_fields(values: dict[str, time | None]) -> list[str]:
    return [field for field, value in values.items() if value is not None]


def create_schedule_exception(*, actor_user_id: int, academic_year_id: int,
                               exception_date: str | date, scope: str, class_id: int | None,
                               exception_type: str, checkin_start: str | None = None,
                               late_after: str | None = None, checkin_cutoff: str | None = None,
                               checkout_start: str | None = None) -> int:
    year_id, day, scope, klass, kind, values = _validate(
        academic_year_id=academic_year_id, exception_date=exception_date, scope=scope,
        class_id=class_id, exception_type=exception_type, checkin_start=checkin_start,
        late_after=late_after, checkin_cutoff=checkin_cutoff, checkout_start=checkout_start,
    )
    try:
        with transaction() as (_, cursor):
            _check_references(cursor, year_id, day, scope, klass)
            cursor.execute(
                """INSERT INTO schedule_exceptions
                   (academic_year_id, exception_date, scope, class_id, exception_type,
                    checkin_start, late_after, checkin_cutoff, checkout_start)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                (year_id, day, scope, klass, kind, *(values[field] for field in OVERRIDE_FIELDS)),
            )
            exception_id = int(cursor.lastrowid)
            record_audit(cursor, actor_user_id=actor_user_id, action="schedule_exception_created",
                         target_type="schedule_exception", target_id=exception_id,
                         metadata={"class_id_present": klass is not None,
                                   "is_active": True,
                                   "fields": _audit_fields(values) + ["exception_date", "scope", "exception_type"]})
    except IntegrityError as error:
        raise _translate_conflict(error) from None
    return exception_id


def update_schedule_exception(*, actor_user_id: int, exception_id: int,
                              academic_year_id: int, exception_date: str | date,
                              scope: str, class_id: int | None, exception_type: str,
                              checkin_start: str | None = None, late_after: str | None = None,
                              checkin_cutoff: str | None = None,
                              checkout_start: str | None = None) -> None:
    exception_id = _positive_id(exception_id, "Exception")
    year_id, day, scope, klass, kind, values = _validate(
        academic_year_id=academic_year_id, exception_date=exception_date, scope=scope,
        class_id=class_id, exception_type=exception_type, checkin_start=checkin_start,
        late_after=late_after, checkin_cutoff=checkin_cutoff, checkout_start=checkout_start,
    )
    try:
        with transaction() as (_, cursor):
            cursor.execute("SELECT id FROM schedule_exceptions WHERE id=%s FOR UPDATE", (exception_id,))
            if cursor.fetchone() is None:
                raise ScheduleExceptionNotFoundError("Exception jadwal tidak ditemukan.")
            _check_references(cursor, year_id, day, scope, klass)
            cursor.execute(
                """UPDATE schedule_exceptions SET academic_year_id=%s, exception_date=%s,
                          scope=%s, class_id=%s, exception_type=%s, checkin_start=%s,
                          late_after=%s, checkin_cutoff=%s, checkout_start=%s WHERE id=%s""",
                (year_id, day, scope, klass, kind, *(values[field] for field in OVERRIDE_FIELDS), exception_id),
            )
            record_audit(cursor, actor_user_id=actor_user_id, action="schedule_exception_updated",
                         target_type="schedule_exception", target_id=exception_id,
                         metadata={"class_id_present": klass is not None,
                                   "fields": _audit_fields(values) + ["exception_date", "scope", "exception_type"]})
    except IntegrityError as error:
        raise _translate_conflict(error) from None


def set_schedule_exception_active(*, actor_user_id: int, exception_id: int,
                                  is_active: bool) -> None:
    exception_id = _positive_id(exception_id, "Exception")
    if type(is_active) is not bool:
        raise ScheduleExceptionError("Status exception tidak valid.")
    with transaction() as (_, cursor):
        cursor.execute("SELECT is_active FROM schedule_exceptions WHERE id=%s FOR UPDATE", (exception_id,))
        item = cursor.fetchone()
        if item is None:
            raise ScheduleExceptionNotFoundError("Exception jadwal tidak ditemukan.")
        cursor.execute("UPDATE schedule_exceptions SET is_active=%s WHERE id=%s", (is_active, exception_id))
        if bool(item["is_active"]) != is_active:
            record_audit(cursor, actor_user_id=actor_user_id,
                         action="schedule_exception_activated" if is_active else "schedule_exception_deactivated",
                         target_type="schedule_exception", target_id=exception_id,
                         metadata={"is_active": is_active})


def resolve_effective_schedule(for_date: date, academic_year_id: int | None = None,
                               class_id: int | None = None) -> dict[str, Any] | None:
    if not isinstance(for_date, date) or isinstance(for_date, datetime):
        raise ScheduleExceptionError("Tanggal jadwal tidak valid.")
    year_id = None if academic_year_id is None else _positive_id(academic_year_id, "Tahun ajaran")
    klass = None if class_id is None else _positive_id(class_id, "Kelas")
    with get_db().cursor() as cursor:
        if year_id is None:
            cursor.execute(
                """SELECT id FROM academic_years WHERE is_active=1 AND start_date<=%s AND end_date>=%s
                   ORDER BY start_date DESC, id DESC LIMIT 1""", (for_date, for_date)
            )
            year = cursor.fetchone()
            if year is None:
                return None
            year_id = int(year["id"])
        cursor.execute("SELECT start_date, end_date FROM academic_years WHERE id=%s LIMIT 1", (year_id,))
        year = cursor.fetchone()
        if year is None or for_date < year["start_date"] or for_date > year["end_date"]:
            return None
        if klass is not None:
            cursor.execute("SELECT academic_year_id FROM classes WHERE id=%s LIMIT 1", (klass,))
            row = cursor.fetchone()
            if row is None or int(row["academic_year_id"]) != year_id:
                raise ScheduleExceptionError("Kelas tidak termasuk dalam tahun ajaran yang dipilih.")
        cursor.execute(
            """SELECT id AS exception_id, scope, class_id, exception_type,
                      TIME_FORMAT(checkin_start, '%%H:%%i') AS checkin_start,
                      TIME_FORMAT(late_after, '%%H:%%i') AS late_after,
                      TIME_FORMAT(checkin_cutoff, '%%H:%%i') AS checkin_cutoff,
                      TIME_FORMAT(checkout_start, '%%H:%%i') AS checkout_start
               FROM schedule_exceptions
               WHERE academic_year_id=%s AND exception_date=%s AND is_active=1
                 AND (scope='school' OR (scope='class' AND class_id=%s))
               ORDER BY CASE WHEN scope='class' THEN 0 ELSE 1 END LIMIT 2""",
            (year_id, for_date, klass or 0),
        )
        exceptions = list(cursor.fetchall())
    effective = resolve_regular_schedule(for_date, year_id)
    if effective is None and not exceptions:
        return None
    result = dict(effective or {field: None for field in OVERRIDE_FIELDS})
    result.update({"academic_year_id": year_id, "class_id": klass, "for_date": for_date,
                   "is_holiday": False, "source": "regular", "exception_id": None,
                   "exception_type": None})
    # Higher-scope values win field by field; unspecified values inherit from the next source.
    for field in OVERRIDE_FIELDS:
        for exception in exceptions:
            if exception[field] is not None:
                result[field] = exception[field]
                break
    for exception in exceptions:
        if result["source"] == "regular":
            result.update({"source": exception["scope"], "exception_id": exception["exception_id"],
                           "exception_type": exception["exception_type"]})
            result["is_holiday"] = exception["exception_type"] == "holiday"
    effective_times = [result.get(field) for field in OVERRIDE_FIELDS]
    if not result["is_holiday"] and any(value is None for value in effective_times):
        raise ScheduleExceptionError("Jadwal non-libur harus memiliki keempat waktu efektif.")
    present_times = [time.fromisoformat(value) if isinstance(value, str) else value
                     for value in effective_times if value is not None]
    if any(left > right for left, right in zip(present_times, present_times[1:])):
        raise ScheduleExceptionError("Gabungan exception menghasilkan urutan waktu yang tidak valid.")
    return result
