"""K-Means input aggregation from immutable school-day snapshots (T27)."""

from __future__ import annotations

import calendar
from datetime import date, datetime, timedelta
from typing import Any

from flask import current_app

from app.database import get_db
from app.services.schedule_service import application_now, resolve_schedules


VALID_STATUSES = {"present", "late", "permit", "sick", "absent"}


class KMeansAggregationError(ValueError):
    """Period, snapshot, or student data cannot be used for analysis."""


def parse_iso_date(value: Any, label: str) -> date:
    if not isinstance(value, str):
        raise KMeansAggregationError(f"{label} tidak valid.")
    try:
        parsed = date.fromisoformat(value)
    except ValueError:
        raise KMeansAggregationError(f"{label} tidak valid.") from None
    if parsed.isoformat() != value:
        raise KMeansAggregationError(f"{label} tidak valid.")
    return parsed


def validate_period(start: date, end: date, year_start: date,
                    year_end: date, today: date) -> tuple[date, date]:
    """Require an ordered, past range contained within one ended academic year."""

    if any(not isinstance(value, date) or isinstance(value, datetime)
           for value in (start, end, year_start, year_end, today)):
        raise KMeansAggregationError("Tanggal periode tidak valid.")
    if start > end:
        raise KMeansAggregationError("Tanggal awal harus sebelum atau sama dengan tanggal akhir.")
    if year_end >= today:
        raise KMeansAggregationError("Analisis hanya tersedia untuk tahun ajaran yang sudah berakhir.")
    if start < year_start or end > year_end:
        raise KMeansAggregationError("Periode harus berada dalam satu tahun ajaran.")
    if end >= today:
        raise KMeansAggregationError("Tanggal akhir periode harus sudah berlalu.")
    return start, end


def calculate_student_features(days: list[dict[str, Any]]) -> dict[str, Any]:
    """Calculate attendance_percentage, late_count, alpha_count for one student."""

    scheduled_school_days = 0
    present_count = 0
    late_count = 0
    permit_count = 0
    sick_count = 0
    alpha_count = 0
    reconstructed_days = 0

    for day in days:
        if "requires_attendance" not in day:
            raise KMeansAggregationError("Snapshot hari wajib hadir belum tersedia.")
        required = day["requires_attendance"]
        if not isinstance(required, (bool, int)) or required not in (0, 1):
            raise KMeansAggregationError("Snapshot hari presensi tidak valid.")
        if day.get("source") not in {
            "attendance_transaction", "manual_status", "finalization_job", "reconstructed",
        }:
            raise KMeansAggregationError("Snapshot hari presensi tidak valid.")
        if day["source"] == "reconstructed":
            reconstructed_days += 1
        if not bool(required):
            if day.get("status") is not None:
                raise KMeansAggregationError(
                    "Status tersimpan bertentangan dengan snapshot hari tanpa kewajiban hadir. "
                    "Periksa konsistensi histori sebelum analisis.")
            continue
        scheduled_school_days += 1
        status = day.get("status")
        if status is None:
            raise KMeansAggregationError("Periode belum lengkap: status hari wajib hadir belum tercatat.")
        if status not in VALID_STATUSES:
            raise KMeansAggregationError("Data status presensi tidak valid untuk analisis.")
        if status == "present":
            present_count += 1
        elif status == "late":
            late_count += 1
        elif status == "permit":
            permit_count += 1
        elif status == "sick":
            sick_count += 1
        elif status == "absent":
            alpha_count += 1

    effective_days = scheduled_school_days - permit_count - sick_count
    if effective_days <= 0:
        return {
            "scheduled_school_days": scheduled_school_days,
            "effective_days": effective_days,
            "attendance_percentage": None,
            "late_count": late_count,
            "alpha_count": alpha_count,
            "eligible": False,
            "ineligible_reason": "zero_effective_days",
            "reconstructed_days": reconstructed_days,
        }
    percentage = round((present_count + late_count) / effective_days * 100, 4)
    return {
        "scheduled_school_days": scheduled_school_days,
        "effective_days": effective_days,
        "attendance_percentage": percentage,
        "late_count": late_count,
        "alpha_count": alpha_count,
        "eligible": True,
        "ineligible_reason": None,
        "reconstructed_days": reconstructed_days,
    }


def _days_between(start: date, end: date) -> list[date]:
    count = (end - start).days
    return [start + timedelta(days=index) for index in range(count + 1)]


def _month_chunks(start: date, end: date):
    current = start
    while current <= end:
        last = date(current.year, current.month,
                    calendar.monthrange(current.year, current.month)[1])
        chunk_end = min(last, end)
        yield current, chunk_end
        current = chunk_end + timedelta(days=1)


def reconstruct_missing_snapshots(*, year_id: int | None = None,
                                  today: date | None = None) -> dict[str, int]:
    """Backfill closed historical class/date snapshots, preserving existing rows."""

    current_day = application_now().date() if today is None else today
    if not isinstance(current_day, date) or isinstance(current_day, datetime):
        raise KMeansAggregationError("Tanggal rekonstruksi tidak valid.")
    db = get_db()
    with db.cursor() as cursor:
        if year_id is None:
            cursor.execute(
                """SELECT id,start_date,end_date FROM academic_years
                   WHERE end_date < %s ORDER BY id""", (current_day,))
        else:
            if not isinstance(year_id, int) or year_id <= 0:
                raise KMeansAggregationError("Tahun ajaran tidak valid.")
            cursor.execute(
                """SELECT id,start_date,end_date FROM academic_years
                   WHERE id=%s AND end_date < %s""", (year_id, current_day))
        years = list(cursor.fetchall())
    if year_id is not None and not years:
        raise KMeansAggregationError("Tahun ajaran tidak ditemukan atau belum berakhir.")

    summary = {"years": 0, "classes": 0, "inserted": 0, "preserved": 0}
    for year in years:
        academic_year_id = int(year["id"])
        cursor_date = year["start_date"]
        end_date = min(year["end_date"], current_day - timedelta(days=1))
        if cursor_date > end_date:
            continue
        with db.cursor() as cursor:
            cursor.execute(
                """SELECT DISTINCT c.id AS class_id
                   FROM classes AS c
                   JOIN student_class_enrollments AS sce ON sce.class_id=c.id
                   WHERE sce.academic_year_id=%s
                   ORDER BY c.id""", (academic_year_id,))
            classes = [int(row["class_id"]) for row in cursor.fetchall()]
        summary["years"] += 1
        for class_id in classes:
            summary["classes"] += 1
            with db.cursor() as cursor:
                for chunk_start, chunk_end in _month_chunks(cursor_date, end_date):
                    dates = _days_between(chunk_start, chunk_end)
                    schedules = resolve_schedules(dates, academic_year_id, class_id)
                    for snapshot_date in dates:
                        required = bool(
                            schedules.get(snapshot_date) is not None
                            and not schedules[snapshot_date].get("is_holiday")
                        )
                        cursor.execute(
                            """INSERT IGNORE INTO attendance_day_snapshots
                               (academic_year_id,class_id,attendance_date,requires_attendance,source)
                               VALUES (%s,%s,%s,%s,'reconstructed')""",
                            (academic_year_id, class_id, snapshot_date, int(required)),
                        )
                        summary["inserted"] += int(cursor.rowcount == 1)
                        summary["preserved"] += int(cursor.rowcount == 0)
            db.commit()
    current_app.logger.info(
        "kmeans.snapshot_backfill years=%s classes=%s inserted=%s preserved=%s",
        summary["years"], summary["classes"], summary["inserted"], summary["preserved"])
    return summary


def aggregate_period(*, year_id: int, start_value: Any, end_value: Any,
                     today: date | None = None) -> dict[str, Any]:
    """Aggregate a complete historical period using student placements and frozen days."""

    if not isinstance(year_id, int) or isinstance(year_id, bool) or year_id <= 0:
        raise KMeansAggregationError("Tahun ajaran tidak valid.")
    start = parse_iso_date(start_value, "Tanggal awal")
    end = parse_iso_date(end_value, "Tanggal akhir")
    current_day = application_now().date() if today is None else today
    db = get_db()
    with db.cursor() as cursor:
        cursor.execute(
            """SELECT id,name,start_date,end_date FROM academic_years WHERE id=%s LIMIT 1""",
            (year_id,))
        year = cursor.fetchone()
    if year is None:
        raise KMeansAggregationError("Tahun ajaran tidak ditemukan.")
    validate_period(start, end, year["start_date"], year["end_date"], current_day)
    total_dates = (end - start).days + 1

    with db.cursor() as cursor:
        cursor.execute(
            """SELECT sce.class_id
               FROM student_class_enrollments AS sce
               WHERE sce.academic_year_id=%s
               GROUP BY sce.class_id ORDER BY sce.class_id""", (year_id,))
        class_ids = [int(row["class_id"]) for row in cursor.fetchall()]
        if not class_ids:
            raise KMeansAggregationError("Tidak ada penempatan siswa pada tahun ajaran ini.")
        placeholders = ",".join(["%s"] * len(class_ids))
        cursor.execute(
            f"""SELECT class_id,COUNT(*) AS snapshot_days
                FROM attendance_day_snapshots
                WHERE academic_year_id=%s AND class_id IN ({placeholders})
                  AND attendance_date BETWEEN %s AND %s
                GROUP BY class_id""",
            (year_id, *class_ids, start, end),
        )
        coverage = {int(row["class_id"]): int(row["snapshot_days"])
                    for row in cursor.fetchall()}
    missing_classes = [class_id for class_id in class_ids
                       if coverage.get(class_id, 0) != total_dates]
    if missing_classes:
        raise KMeansAggregationError(
            "Periode belum lengkap: snapshot hari kelas belum tersedia. Jalankan rekonstruksi historis.")

    with db.cursor() as cursor:
        cursor.execute(
            """SELECT sce.student_id,s.full_name,s.nisn,sce.class_id,c.name AS class_name,
                      ds.attendance_date,ds.requires_attendance,ds.source AS snapshot_source,
                      ar.id AS record_id, ar.class_id AS record_class_id, ar.status
               FROM student_class_enrollments AS sce
               JOIN students AS s ON s.id=sce.student_id
               JOIN classes AS c ON c.id=sce.class_id
               JOIN attendance_day_snapshots AS ds
                 ON ds.academic_year_id=sce.academic_year_id
                AND ds.class_id=sce.class_id
               LEFT JOIN attendance_records AS ar
                 ON ar.student_id=sce.student_id AND ar.attendance_date=ds.attendance_date
               WHERE sce.academic_year_id=%s
                 AND ds.attendance_date BETWEEN %s AND %s
               ORDER BY sce.class_id,sce.student_id,ds.attendance_date""",
            (year_id, start, end),
        )
        raw_rows = list(cursor.fetchall())

    students: dict[int, dict[str, Any]] = {}
    for row in raw_rows:
        if row["record_id"] is not None and (
                row["record_class_id"] is None
                or int(row["record_class_id"]) != int(row["class_id"])):
            raise KMeansAggregationError(
                "Snapshot kelas record tidak sesuai dengan penempatan siswa. "
                "Periksa konsistensi histori sebelum analisis.")
        student_id = int(row["student_id"])
        student = students.setdefault(student_id, {
            "student_id": student_id,
            "full_name": str(row["full_name"]),
            "nisn": str(row["nisn"]),
            "class_id": int(row["class_id"]),
            "class_name": str(row["class_name"]),
            "days": [],
        })
        student["days"].append({
            "requires_attendance": bool(row["requires_attendance"]),
            "status": row["status"],
            "source": row["snapshot_source"],
        })

    results: list[dict[str, Any]] = []
    reconstructed_dates = {
        row["attendance_date"] for row in raw_rows
        if row["snapshot_source"] == "reconstructed"
    }
    for student in students.values():
        features = calculate_student_features(student.pop("days"))
        results.append({**student, **features})
    results.sort(key=lambda item: (item["class_name"].casefold(), item["full_name"].casefold(), item["student_id"]))
    return {
        "academic_year_id": year_id,
        "academic_year_name": year["name"],
        "start_date": start,
        "end_date": end,
        "total_dates": total_dates,
        "reconstructed_snapshot_dates": len(reconstructed_dates),
        "students": results,
        "eligible_students": sum(bool(item["eligible"]) for item in results),
        "ineligible_students": sum(not bool(item["eligible"]) for item in results),
    }
