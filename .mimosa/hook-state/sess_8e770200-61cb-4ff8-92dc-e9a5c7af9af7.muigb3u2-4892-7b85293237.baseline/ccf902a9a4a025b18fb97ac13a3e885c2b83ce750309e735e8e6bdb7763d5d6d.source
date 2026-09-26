"""Finalisasi Alpa after the effective check-in cutoff (T20, PRD 11.4, BR-13/14).

The job marks a student absent only when all of the following hold for the
target date: the student has an active placement in an active class/year, the
effective schedule exists and is not a holiday, the moment is strictly after
that schedule's check-in cutoff, and the student has neither auto-presence nor
any stored status. Decisions are pure (``decide_finalization``) so boundaries
are testable with a controlled clock; writes re-validate under row locks so a
concurrent check-in or teacher status always wins.
"""

from __future__ import annotations

from datetime import date, datetime, time
from typing import Any

from flask import current_app
from pymysql import IntegrityError

from app.database import get_db, transaction
from app.services.attendance_day_snapshot_service import (
    ensure_day_snapshot,
    snapshot_requires_closure,
)
from app.services.audit_service import record_audit
from app.services.schedule_service import application_now, resolve_schedule


REASONS = ("no_schedule", "holiday", "before_cutoff", "has_presence",
           "has_manual_status", "raced")


class FinalizationError(ValueError):
    """Invalid finalization input or configuration."""


def _cutoff_time(schedule: dict[str, Any]) -> time:
    value = schedule["checkin_cutoff"]
    if isinstance(value, time):
        return value
    try:
        return time.fromisoformat(str(value))
    except ValueError:
        raise FinalizationError("Cutoff jadwal efektif tidak valid.") from None


def decide_finalization(*, schedule: dict[str, Any] | None,
                        record: dict[str, Any] | None,
                        at: datetime, for_date: date) -> tuple[str, str]:
    """Pure decision for one student/date: ("finalize", "") or ("skip", reason).

    ``at`` and ``for_date`` are separate so backfilling an earlier date is not
    blocked by today's time of day. Cutoff is inclusive for check-in (the
    student may still check in exactly at cutoff), so finalization requires a
    moment strictly after it.
    """

    if schedule is None:
        return "skip", "no_schedule"
    if schedule.get("is_holiday"):
        return "skip", "holiday"
    if for_date > at.date():
        return "skip", "before_cutoff"
    if for_date == at.date():
        current_time = at.timetz().replace(tzinfo=None) if isinstance(at, datetime) else at
        if current_time <= _cutoff_time(schedule):
            return "skip", "before_cutoff"
    # The cutoff for this date has passed: only the record can still exempt.
    if record:
        if record.get("checkin_at") is not None:
            return "skip", "has_presence"
        if record.get("status") is not None:
            return "skip", "has_manual_status"
    return "finalize", ""


def _candidates(cursor, for_date: date) -> list[dict[str, Any]]:
    """Students required to attend: active account, placement, class, and year."""

    cursor.execute(
        """SELECT s.id AS student_id, sce.class_id, sce.academic_year_id
           FROM student_class_enrollments AS sce
           JOIN students AS s ON s.id = sce.student_id
           JOIN users AS u ON u.id = s.user_id
           JOIN classes AS c ON c.id = sce.class_id
           JOIN academic_years AS ay ON ay.id = sce.academic_year_id
           WHERE u.role = 'student' AND u.is_active = 1
             AND c.is_active = 1 AND ay.is_active = 1
             AND ay.start_date <= %s AND ay.end_date >= %s""",
        (for_date, for_date),
    )
    return list(cursor.fetchall())


def _snapshot_classes(cursor, for_date: date) -> list[dict[str, int]]:
    """Classes with a placement in the active year, including inactive students."""

    cursor.execute(
        """SELECT DISTINCT sce.academic_year_id, sce.class_id
           FROM student_class_enrollments AS sce
           JOIN classes AS c ON c.id=sce.class_id
           JOIN academic_years AS ay ON ay.id=sce.academic_year_id
           WHERE c.is_active=1 AND ay.is_active=1
             AND ay.start_date<=%s AND ay.end_date>=%s
           ORDER BY sce.academic_year_id,sce.class_id""",
        (for_date, for_date),
    )
    return list(cursor.fetchall())


def _load_records(cursor, for_date: date) -> dict[int, dict[str, Any]]:
    cursor.execute(
        """SELECT student_id, status, status_source, checkin_at
           FROM attendance_records WHERE attendance_date = %s""",
        (for_date,),
    )
    return {int(row["student_id"]): row for row in cursor.fetchall()}


def _write_alpa(*, schedule: dict[str, Any], student_id: int,
                academic_year_id: int, class_id: int,
                for_date: date, at: datetime) -> tuple[str, str]:
    """Write one Alpa under row locks; re-validate so races never overwrite.

    Returns ("finalized", "") or ("skipped", reason). IntegrityError from a
    concurrent check-in insert is translated to a skip, never a failure.
    """

    try:
        with transaction() as (_, cursor):
            cursor.execute(
                """SELECT id, status, status_source, checkin_at
                   FROM attendance_records
                   WHERE student_id = %s AND attendance_date = %s
                   LIMIT 1 FOR UPDATE""",
                (student_id, for_date),
            )
            row = cursor.fetchone()
            decision, reason = decide_finalization(
                schedule=schedule, record=row, at=at, for_date=for_date)
            if decision == "skip":
                return "skipped", reason
            if row is None:
                cursor.execute(
                    """INSERT INTO attendance_records
                       (student_id, class_id, attendance_date, status, status_source)
                       VALUES (%s, %s, %s, 'absent', 'finalization_job')""",
                    (student_id, class_id, for_date),
                )
                record_id = int(cursor.lastrowid)
            else:
                cursor.execute(
                    """UPDATE attendance_records
                       SET status='absent', status_source='finalization_job',
                           class_id=COALESCE(class_id, %s)
                       WHERE id=%s AND status IS NULL AND checkin_at IS NULL""",
                    (class_id, row["id"]),
                )
                if cursor.rowcount != 1:
                    return "skipped", "raced"
                record_id = int(row["id"])
            ensure_day_snapshot(
                cursor, academic_year_id=academic_year_id, class_id=class_id,
                for_date=for_date, schedule=schedule, source="finalization_job",
            )
            record_audit(cursor, actor_user_id=None,
                         action="attendance_alpa_finalized",
                         target_type="attendance_record", target_id=record_id)
    except IntegrityError:
        # A check-in won the UNIQUE (student_id, attendance_date) race.
        return "skipped", "raced"
    return "finalized", ""


def finalize_alpa(*, for_date: date | None = None, at: datetime | None = None,
                  dry_run: bool = False) -> dict[str, Any]:
    """Run finalization for one date and return counts only (no personal data)."""

    moment = application_now() if at is None else at
    target = moment.date() if for_date is None else for_date
    if not isinstance(target, date) or isinstance(target, datetime):
        raise FinalizationError("Tanggal finalisasi tidak valid.")

    summary: dict[str, Any] = {
        "date": target.isoformat(), "dry_run": bool(dry_run),
        "candidates": 0, "processed": 0, "skipped": 0, "failed": 0,
        "skip_reasons": {reason: 0 for reason in REASONS},
    }

    with get_db().cursor() as cursor:
        candidates = _candidates(cursor, target)
        records = _load_records(cursor, target)
        snapshot_classes = _snapshot_classes(cursor, target)
    summary["candidates"] = len(candidates)

    groups: dict[tuple[int, int], list[dict[str, Any]]] = {}
    for row in candidates:
        groups.setdefault((int(row["academic_year_id"]), int(row["class_id"])), []).append(row)

    for snapshot_class in snapshot_classes:
        groups.setdefault((int(snapshot_class["academic_year_id"]),
                           int(snapshot_class["class_id"])), [])

    for (year_id, class_id), rows in groups.items():
        try:
            schedule = resolve_schedule(target, year_id, class_id)
        except Exception:
            current_app.logger.exception(
                "finalisasi.schedule_failed year_id=%s class_id=%s", year_id, class_id)
            summary["failed"] += len(rows)
            continue
        if not dry_run and snapshot_requires_closure(
                schedule=schedule, for_date=target, at=moment):
            try:
                with transaction() as (_, cursor):
                    ensure_day_snapshot(
                        cursor, academic_year_id=year_id, class_id=class_id,
                        for_date=target, schedule=schedule, source="finalization_job",
                    )
            except Exception:
                summary["failed"] += len(rows) or 1
                current_app.logger.exception(
                    "finalisasi.snapshot_failed year_id=%s class_id=%s", year_id, class_id)
                continue
        for row in rows:
            student_id = int(row["student_id"])
            record = records.get(student_id)
            decision, reason = decide_finalization(
                schedule=schedule, record=record, at=moment, for_date=target)
            if decision == "skip":
                summary["skipped"] += 1
                summary["skip_reasons"][reason] += 1
                continue
            if dry_run:
                summary["processed"] += 1
                continue
            try:
                outcome, outcome_reason = _write_alpa(
                    schedule=schedule, student_id=student_id, academic_year_id=year_id,
                    class_id=class_id,
                    for_date=target, at=moment)
            except Exception:
                summary["failed"] += 1
                current_app.logger.exception(
                    "finalisasi.student_failed student_id=%s", student_id)
                continue
            if outcome == "finalized":
                summary["processed"] += 1
            else:
                summary["skipped"] += 1
                summary["skip_reasons"][outcome_reason] += 1
    return summary
