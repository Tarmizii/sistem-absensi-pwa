"""Immutable school-day snapshots used by period analytics (T27)."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any


SNAPSHOT_SOURCES = {
    "attendance_transaction", "manual_status", "finalization_job", "reconstructed",
}


def ensure_day_snapshot(cursor: Any, *, academic_year_id: int, class_id: int,
                        for_date: date, schedule: dict[str, Any] | None,
                        source: str) -> bool:
    """Insert the first immutable day interpretation for a class/date.

    The caller owns the transaction so an attendance/status write and its
    first snapshot commit or roll back together. Duplicate inserts never
    update a snapshot made earlier under a different schedule.
    """

    if (not isinstance(for_date, date) or isinstance(for_date, datetime)
            or academic_year_id <= 0 or class_id <= 0 or source not in SNAPSHOT_SOURCES):
        raise ValueError("Snapshot hari presensi tidak valid.")
    required = schedule is not None and not bool(schedule.get("is_holiday"))
    cursor.execute(
        """INSERT IGNORE INTO attendance_day_snapshots
           (academic_year_id,class_id,attendance_date,requires_attendance,source)
           VALUES (%s,%s,%s,%s,%s)""",
        (academic_year_id, class_id, for_date, int(required), source),
    )
    return cursor.rowcount == 1


def snapshot_requires_closure(*, schedule: dict[str, Any] | None,
                              for_date: date, at: datetime) -> bool:
    """Whether finalization has enough information to freeze this date.

    A missing schedule or holiday has no attendance cutoff, so it can be
    closed on the day finalization visits it. A school day closes only after
    its inclusive check-in cutoff (or after that calendar date).
    """

    if for_date > at.date():
        return False
    if schedule is None or bool(schedule.get("is_holiday")):
        return True
    cutoff = schedule.get("checkin_cutoff")
    if isinstance(cutoff, str):
        from datetime import time
        cutoff = time.fromisoformat(cutoff)
    if not hasattr(cutoff, "hour"):
        return False
    current_time = at.timetz().replace(tzinfo=None)
    return for_date < at.date() or current_time > cutoff
