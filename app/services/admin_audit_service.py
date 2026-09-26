"""Admin-only, privacy-limited audit-log read model (T26)."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
import re
from typing import Any

from app.database import get_db
from app.services.attendance_read_service import (
    AttendanceReadError,
    PAGE_SIZE,
    escape_like_pattern,
    parse_page,
)
from app.services.audit_service import AUDIT_ACTIONS
from app.services.schedule_service import app_timezone


_DATE_PATTERN = re.compile(r"\d{4}-\d{2}-\d{2}\Z")


def _parse_date(value: str | None, label: str) -> date | None:
    if value in (None, ""):
        return None
    if not isinstance(value, str) or not _DATE_PATTERN.fullmatch(value):
        raise AttendanceReadError(f"Filter {label} harus memakai format YYYY-MM-DD.")
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise AttendanceReadError(f"Filter {label} tidak valid.") from None


def _local_day_utc_start(day: date) -> datetime:
    return datetime.combine(day, time.min, tzinfo=app_timezone()).astimezone(
        timezone.utc
    ).replace(tzinfo=None)


def _where(actor: str, date_from: date | None, date_to: date | None,
           action: str) -> tuple[str, tuple[Any, ...]]:
    clauses: list[str] = []
    params: list[Any] = []
    if actor:
        clauses.append(
            "(u.username LIKE %s ESCAPE '\\\\' OR COALESCE(t.full_name,'') LIKE %s ESCAPE '\\\\' "
            "OR COALESCE(s.full_name,'') LIKE %s ESCAPE '\\\\')"
        )
        term = f"%{escape_like_pattern(actor)}%"
        params.extend((term, term, term))
    if date_from:
        clauses.append("al.created_at >= %s")
        try:
            params.append(_local_day_utc_start(date_from))
        except (OverflowError, ValueError):
            raise AttendanceReadError("Filter tanggal awal di luar rentang yang didukung.") from None
    if date_to:
        clauses.append("al.created_at < %s")
        try:
            params.append(_local_day_utc_start(date_to + timedelta(days=1)))
        except (OverflowError, ValueError):
            raise AttendanceReadError("Filter tanggal akhir di luar rentang yang didukung.") from None
    if action:
        clauses.append("al.action=%s")
        params.append(action)
    return (" AND ".join(clauses) if clauses else "1=1", tuple(params))


def _format_created_at(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(app_timezone()).strftime("%Y-%m-%d %H:%M")


def get_admin_audit_logs(actor_value: str | None, from_value: str | None,
                         to_value: str | None, action_value: str | None,
                         page_value: str | None) -> dict[str, Any]:
    """List safe event headers; free-form metadata is intentionally omitted."""
    actor = actor_value or ""
    if (not isinstance(actor, str) or len(actor) > 100
            or any(ord(char) < 32 for char in actor)):
        raise AttendanceReadError("Filter pelaku tidak valid.")
    actor = actor.strip()
    date_from = _parse_date(from_value, "tanggal awal")
    date_to = _parse_date(to_value, "tanggal akhir")
    if date_from and date_to and date_from > date_to:
        raise AttendanceReadError("Tanggal awal tidak boleh melewati tanggal akhir.")
    action = action_value or ""
    if action and action not in AUDIT_ACTIONS:
        raise AttendanceReadError("Filter aksi tidak valid.")
    page = parse_page(page_value)
    where_sql, params = _where(actor, date_from, date_to, action)
    joins = """FROM audit_logs AS al
        LEFT JOIN users AS u ON u.id=al.actor_user_id
        LEFT JOIN teachers AS t ON t.user_id=u.id
        LEFT JOIN students AS s ON s.user_id=u.id"""
    with get_db().cursor() as cursor:
        cursor.execute(
            f"""SELECT COUNT(*) AS total {joins} WHERE {where_sql}""",
            params,
        )
        total = int(cursor.fetchone()["total"])
        pages = (total + PAGE_SIZE - 1) // PAGE_SIZE
        page = min(page, max(pages, 1))
        cursor.execute(
            f"""SELECT al.id AS audit_id, al.action, al.target_type,
                       al.target_id, al.created_at,
                       COALESCE(t.full_name, s.full_name, u.username, 'Sistem') AS actor_label
                {joins}
                WHERE {where_sql}
                ORDER BY al.created_at DESC, al.id DESC
                LIMIT %s OFFSET %s""",
            (*params, PAGE_SIZE, (page - 1) * PAGE_SIZE),
        )
        rows = list(cursor.fetchall())
    for row in rows:
        row["created_at"] = _format_created_at(row["created_at"])
    return {
        "rows": rows, "actor": actor,
        "date_from": date_from.isoformat() if date_from else "",
        "date_to": date_to.isoformat() if date_to else "",
        "action": action, "actions": sorted(AUDIT_ACTIONS),
        "page": page, "pages": pages, "total": total,
    }
