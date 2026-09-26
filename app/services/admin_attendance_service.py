"""Global Admin attendance read models (T25)."""

from __future__ import annotations

from datetime import date, datetime
import re
from typing import Any

from app.database import get_db
from app.services.attendance_read_service import (
    AttendanceReadError,
    PAGE_SIZE,
    STORED_STATUSES,
    escape_like_pattern,
    parse_month,
    parse_page,
)
from app.services.schedule_service import (
    application_now,
    database_datetime_to_local_time,
)


_DATE_PATTERN = re.compile(r"\d{4}-\d{2}-\d{2}\Z")
_STATUS_LABELS = {
    "present": "Hadir", "late": "Terlambat", "permit": "Izin",
    "sick": "Sakit", "absent": "Alpa",
}
_SOURCE_LABELS = {"system": "Sistem", "teacher": "Guru", "finalization_job": "Sistem"}
_JOURNAL_COLUMNS = """ar.id AS record_id, ar.class_id, ar.attendance_date,
    ar.status, ar.status_source, ar.notes, ar.checkin_at, ar.checkout_at,
    c.name AS class_name, s.id AS student_id, s.full_name, s.nisn"""


def _parse_date(value: str | None, at: datetime | None = None) -> date:
    if value in (None, ""):
        return (application_now() if at is None else at).date()
    if not isinstance(value, str) or not _DATE_PATTERN.fullmatch(value):
        raise AttendanceReadError("Tanggal harus memakai format YYYY-MM-DD.")
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise AttendanceReadError("Tanggal tidak valid.") from None


def _parse_class_id(value: str | None) -> int | None:
    if value in (None, ""):
        return None
    if (not isinstance(value, str) or len(value) > 20
            or not value.isascii() or not value.isdecimal()):
        raise AttendanceReadError("Kelas tidak valid.")
    class_id = int(value)
    if class_id < 1:
        raise AttendanceReadError("Kelas tidak valid.")
    return class_id


def _validate_status(value: str | None) -> str:
    status = value or ""
    if status and status not in STORED_STATUSES:
        raise AttendanceReadError("Filter status tidak valid.")
    return status


def _validate_search(value: str | None) -> str:
    query = value or ""
    if (not isinstance(query, str) or len(query) > 100
            or any(ord(char) < 32 for char in query)):
        raise AttendanceReadError("Pencarian tidak valid.")
    return query.strip()


def _list_classes(cursor) -> list[dict[str, Any]]:
    cursor.execute(
        """SELECT c.id AS class_id, c.name AS class_name, c.is_active AS class_active,
                  ay.id AS academic_year_id, ay.name AS academic_year_name,
                  ay.is_active AS academic_year_active, ay.start_date AS academic_year_start,
                  ay.end_date AS academic_year_end
           FROM classes AS c JOIN academic_years AS ay ON ay.id=c.academic_year_id
           ORDER BY ay.start_date DESC, ay.id DESC, c.name, c.id"""
    )
    return list(cursor.fetchall())


def _summary(cursor, selected_date: date, class_id: int | None,
             *, today: bool) -> dict[str, int]:
    summary = {"total": 0, "present": 0, "late": 0, "permit": 0,
               "sick": 0, "absent": 0, "pending": 0}
    if today:
        roster_where = [
            "c.is_active=1", "ay.is_active=1", "ay.start_date<=%s",
            "ay.end_date>=%s", "u.role='student'", "u.is_active=1",
        ]
        roster_params: list[Any] = [selected_date, selected_date]
        if class_id is not None:
            roster_where.append("c.id=%s")
            roster_params.append(class_id)
        cursor.execute(
            f"""SELECT COUNT(DISTINCT s.id) AS total,
                       COUNT(DISTINCT CASE WHEN ar.status='present' THEN s.id END) AS present,
                       COUNT(DISTINCT CASE WHEN ar.status='late' THEN s.id END) AS late,
                       COUNT(DISTINCT CASE WHEN ar.status='permit' THEN s.id END) AS permit,
                       COUNT(DISTINCT CASE WHEN ar.status='sick' THEN s.id END) AS sick,
                       COUNT(DISTINCT CASE WHEN ar.status='absent' THEN s.id END) AS absent,
                       COUNT(DISTINCT CASE WHEN ar.status IS NULL THEN s.id END) AS pending
                FROM student_class_enrollments AS sce
                JOIN classes AS c ON c.id=sce.class_id
                JOIN academic_years AS ay ON ay.id=sce.academic_year_id
                JOIN students AS s ON s.id=sce.student_id
                JOIN users AS u ON u.id=s.user_id
                LEFT JOIN attendance_records AS ar
                       ON ar.student_id=s.id AND ar.attendance_date=%s
                WHERE {' AND '.join(roster_where)}""",
            (selected_date, *roster_params),
        )
        row = cursor.fetchone()
        return {key: int(row[key] or 0) for key in summary}

    where = ["attendance_date=%s"]
    params: list[Any] = [selected_date]
    if class_id is not None:
        where.append("class_id=%s")
        params.append(class_id)
    cursor.execute(
        f"""SELECT status, COUNT(*) AS total FROM attendance_records
            WHERE {' AND '.join(where)} GROUP BY status""",
        tuple(params),
    )
    for row in cursor.fetchall():
        status = row["status"]
        if status in _STATUS_LABELS:
            summary[status] = int(row["total"])
    summary["total"] = sum(summary[key] for key in (
        "present", "late", "permit", "sick", "absent", "pending"
    ))
    return summary


def _validated_journal_filters(date_value: str | None, class_value: str | None,
                               status_value: str | None, query_value: str | None,
                               at: datetime | None = None):
    moment = application_now() if at is None else at
    return (
        moment,
        _parse_date(date_value, moment),
        _parse_class_id(class_value),
        _validate_status(status_value),
        _validate_search(query_value),
    )


def _validate_selected_class(classes: list[dict[str, Any]], class_id: int | None):
    selected = next((item for item in classes
                     if class_id is not None and int(item["class_id"]) == class_id), None)
    if class_id is not None and selected is None:
        raise AttendanceReadError("Kelas tidak ditemukan.")
    return selected


def _journal_where(selected_date: date, class_id: int | None,
                   status: str, query: str) -> tuple[str, tuple[Any, ...]]:
    where = ["ar.attendance_date=%s"]
    params: list[Any] = [selected_date]
    if class_id is not None:
        where.append("ar.class_id=%s")
        params.append(class_id)
    if status:
        where.append("ar.status=%s")
        params.append(status)
    if query:
        where.append("(s.full_name LIKE %s ESCAPE '\\\\' OR s.nisn LIKE %s ESCAPE '\\\\')")
        like = f"%{escape_like_pattern(query)}%"
        params.extend((like, like))
    return " AND ".join(where), tuple(params)


def _select_journal_rows(cursor, where_sql: str, params: tuple[Any, ...],
                         *, limit: int | None = None, offset: int = 0) -> list[dict[str, Any]]:
    sql = f"""SELECT {_JOURNAL_COLUMNS}
              FROM attendance_records AS ar
              JOIN students AS s ON s.id=ar.student_id
              LEFT JOIN classes AS c ON c.id=ar.class_id
              WHERE {where_sql}
              ORDER BY ar.attendance_date DESC, c.name, s.full_name, s.id"""
    if limit is None:
        cursor.execute(sql, params)
    else:
        cursor.execute(sql + " LIMIT %s OFFSET %s", (*params, limit, offset))
    return list(cursor.fetchall())


def _format_journal_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    for row in rows:
        row["date"] = row.pop("attendance_date").isoformat()
        row["status_label"] = _STATUS_LABELS.get(row["status"], "Status belum tercatat")
        row["source_label"] = _SOURCE_LABELS.get(row["status_source"])
        row["checkin_time"] = database_datetime_to_local_time(row.pop("checkin_at"))
        row["checkout_time"] = database_datetime_to_local_time(row.pop("checkout_at"))
    return rows


def get_admin_attendance(date_value: str | None, class_value: str | None,
                         status_value: str | None, query_value: str | None,
                         page_value: str | None, at: datetime | None = None) -> dict[str, Any]:
    """Return one-day summary and a separately filtered, paginated journal.

    Summary cards use date and class only, so journal status/search filters do not
    make the headline counts fluctuate. Today's counts use the active class/year
    roster; a missing stored status is pending and is never inferred as Alpa.
    Older dates count persisted statuses only and never reconstruct a roster.
    """
    moment, selected_date, class_id, status, query = _validated_journal_filters(
        date_value, class_value, status_value, query_value, at
    )
    page = parse_page(page_value)

    with get_db().cursor() as cursor:
        classes = _list_classes(cursor)
        selected = _validate_selected_class(classes, class_id)
        summary = _summary(
            cursor, selected_date, class_id, today=selected_date == moment.date(),
        )

        where_sql, params = _journal_where(selected_date, class_id, status, query)
        cursor.execute(
            f"""SELECT COUNT(*) AS total FROM attendance_records AS ar
                JOIN students AS s ON s.id=ar.student_id
                WHERE {where_sql}""",
            params,
        )
        total = int(cursor.fetchone()["total"])
        pages = (total + PAGE_SIZE - 1) // PAGE_SIZE
        page = min(page, max(pages, 1))
        rows = _select_journal_rows(
            cursor, where_sql, params, limit=PAGE_SIZE, offset=(page - 1) * PAGE_SIZE
        )

    rows = _format_journal_rows(rows)
    return {
        "date": selected_date.isoformat(), "classes": classes,
        "selected_class": selected, "class_id": str(class_id or ""),
        "summary": summary, "rows": rows, "page": page, "pages": pages,
        "total": total, "status": status, "q": query,
        "is_today": selected_date == moment.date(),
    }


def get_admin_attendance_export(date_value: str | None, class_value: str | None,
                                status_value: str | None, query_value: str | None,
                                at: datetime | None = None) -> list[dict[str, Any]]:
    """Return every journal row matching the same filters, without pagination."""
    _, selected_date, class_id, status, query = _validated_journal_filters(
        date_value, class_value, status_value, query_value, at
    )
    with get_db().cursor() as cursor:
        classes = _list_classes(cursor)
        _validate_selected_class(classes, class_id)
        where_sql, params = _journal_where(selected_date, class_id, status, query)
        rows = _select_journal_rows(cursor, where_sql, params)
    return _format_journal_rows(rows)


def get_admin_student_month_history(student_id: int, month_value: str) -> list[dict[str, Any]]:
    """Return stored records only for one student's chosen calendar month."""
    start, end, _ = parse_month(month_value)
    with get_db().cursor() as cursor:
        cursor.execute(
            """SELECT ar.id AS record_id, ar.attendance_date, ar.status,
                      ar.checkin_at, ar.checkout_at, c.name AS class_name
               FROM attendance_records AS ar
               LEFT JOIN classes AS c ON c.id=ar.class_id
               WHERE ar.student_id=%s AND ar.attendance_date>=%s AND ar.attendance_date<%s
               ORDER BY ar.attendance_date DESC, ar.id DESC""",
            (student_id, start, end),
        )
        records = list(cursor.fetchall())
    for record in records:
        record["date"] = record.pop("attendance_date").isoformat()
        record["status_label"] = _STATUS_LABELS.get(record["status"], "Status belum tercatat")
        record["checkin_time"] = database_datetime_to_local_time(record.pop("checkin_at"))
        record["checkout_time"] = database_datetime_to_local_time(record.pop("checkout_at"))
    return records
