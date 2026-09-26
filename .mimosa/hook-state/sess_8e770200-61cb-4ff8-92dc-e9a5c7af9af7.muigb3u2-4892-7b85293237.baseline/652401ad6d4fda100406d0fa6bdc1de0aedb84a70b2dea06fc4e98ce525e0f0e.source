"""Verify T27 snapshot reconstruction and feature aggregation on dev MySQL."""

from __future__ import annotations

from datetime import date, timedelta
import secrets

from werkzeug.security import generate_password_hash

from app import create_app
from app.database import transaction
from app.services.attendance_day_snapshot_service import ensure_day_snapshot
from app.services.kmeans_aggregation_service import (
    KMeansAggregationError,
    aggregate_period,
    reconstruct_missing_snapshots,
)


def main() -> None:
    app = create_app({"TESTING": True})
    if app.config["APP_ENV"] == "production":
        raise SystemExit("Smoke T27 hanya boleh memakai database development/test.")
    suffix = secrets.token_hex(4)
    today = date(2026, 9, 24)
    start = date(2025, 8, 1)
    end = date(2025, 8, 6)
    password_hash = generate_password_hash(f"Smoke-T27-{suffix}-temporary-password")
    user_ids: list[int] = []
    student_ids: list[int] = []
    class_id = year_id = None

    with app.app_context():
        try:
            with transaction() as (_, cursor):
                cursor.execute(
                    """INSERT INTO academic_years (name,start_date,end_date,is_active)
                       VALUES (%s,%s,%s,0)""",
                    (f"T27-{suffix}", start, end),
                )
                year_id = int(cursor.lastrowid)
                cursor.execute(
                    "INSERT INTO classes (academic_year_id,name,is_active) VALUES (%s,%s,1)",
                    (year_id, f"X-T27-{suffix}"),
                )
                class_id = int(cursor.lastrowid)
                for weekday in range(1, 8):
                    cursor.execute(
                        """INSERT INTO attendance_schedules
                           (academic_year_id,day_of_week,checkin_start,late_after,
                            checkin_cutoff,checkout_start,is_active)
                           VALUES (%s,%s,'06:30','07:15','08:00','15:00',1)""",
                        (year_id, weekday),
                    )
                cursor.execute(
                    """INSERT INTO schedule_exceptions
                       (academic_year_id,exception_date,scope,class_id,exception_type,is_active)
                       VALUES (%s,%s,'class',%s,'holiday',1)""",
                    (year_id, start + timedelta(days=2), class_id),
                )
                for label, active in (("aktif", 1), ("nonaktif", 0)):
                    cursor.execute(
                        """INSERT INTO users
                           (username,password_hash,role,is_active,must_change_password)
                           VALUES (%s,%s,'student',%s,0)""",
                        (f"smoke-t27-{label}-{suffix}", password_hash, active),
                    )
                    user_id = int(cursor.lastrowid)
                    user_ids.append(user_id)
                    cursor.execute(
                        """INSERT INTO students (user_id,nisn,full_name,face_registered)
                           VALUES (%s,%s,%s,1)""",
                        (user_id, f"T27{suffix}{len(student_ids):02d}", f"T27 {label} {suffix}"),
                    )
                    student_id = int(cursor.lastrowid)
                    student_ids.append(student_id)
                    cursor.execute(
                        """INSERT INTO student_class_enrollments
                           (student_id,academic_year_id,class_id) VALUES (%s,%s,%s)""",
                        (student_id, year_id, class_id),
                    )

            backfill = reconstruct_missing_snapshots(year_id=year_id, today=today)
            assert backfill["inserted"] == 6 and backfill["preserved"] == 0, backfill
            repeat = reconstruct_missing_snapshots(year_id=year_id, today=today)
            assert repeat["inserted"] == 0 and repeat["preserved"] == 6, repeat

            # A contradictory later resolver result cannot revise the initial snapshot.
            with transaction() as (_, cursor):
                ensure_day_snapshot(
                    cursor, academic_year_id=year_id, class_id=class_id,
                    for_date=start, schedule={"is_holiday": True},
                    source="finalization_job",
                )
                cursor.execute(
                    """SELECT requires_attendance,source FROM attendance_day_snapshots
                       WHERE class_id=%s AND attendance_date=%s""",
                    (class_id, start),
                )
                frozen = cursor.fetchone()
                assert frozen == {"requires_attendance": 1, "source": "reconstructed"}, frozen

            required_dates = [start, start + timedelta(days=1),
                              start + timedelta(days=3), start + timedelta(days=4), end]
            status_sets = [
                ("present", "late", "permit", "sick", "absent"),
                ("permit", "sick", "permit", "sick", "permit"),
            ]
            with transaction() as (_, cursor):
                for student_id, statuses in zip(student_ids, status_sets):
                    for attendance_date, status in zip(required_dates, statuses):
                        cursor.execute(
                            """INSERT INTO attendance_records
                               (student_id,class_id,attendance_date,status,status_source)
                               VALUES (%s,%s,%s,%s,'teacher')""",
                            (student_id, class_id, attendance_date, status),
                        )

            result = aggregate_period(
                year_id=year_id, start_value=start.isoformat(), end_value=end.isoformat(), today=today,
            )
            assert result["reconstructed_snapshot_dates"] == 6, result
            first = next(row for row in result["students"] if row["student_id"] == student_ids[0])
            inactive = next(row for row in result["students"] if row["student_id"] == student_ids[1])
            assert first["scheduled_school_days"] == 5, first
            assert first["effective_days"] == 3, first
            assert first["attendance_percentage"] == 66.6667, first
            assert first["late_count"] == 1 and first["alpha_count"] == 1, first
            assert inactive["eligible"] is False and inactive["attendance_percentage"] is None, inactive
            assert result["eligible_students"] == 1 and result["ineligible_students"] == 1, result

            # Never combine an unscoped record with a placement's day snapshot.
            with transaction() as (_, cursor):
                cursor.execute(
                    "UPDATE attendance_records SET class_id=NULL WHERE student_id=%s AND attendance_date=%s",
                    (student_ids[0], start),
                )
            try:
                aggregate_period(year_id=year_id, start_value=start.isoformat(),
                                 end_value=end.isoformat(), today=today)
            except KMeansAggregationError as error:
                assert "Snapshot kelas" in str(error), error
            else:
                raise AssertionError("Unscoped record was used in analysis.")
            with transaction() as (_, cursor):
                cursor.execute(
                    "UPDATE attendance_records SET class_id=%s WHERE student_id=%s AND attendance_date=%s",
                    (class_id, student_ids[0], start),
                )
                cursor.execute(
                    """INSERT INTO attendance_records
                       (student_id,class_id,attendance_date,status,status_source)
                       VALUES (%s,%s,%s,'late','system')""",
                    (student_ids[0], class_id, start + timedelta(days=2)),
                )
            try:
                aggregate_period(year_id=year_id, start_value=start.isoformat(),
                                 end_value=end.isoformat(), today=today)
            except KMeansAggregationError as error:
                assert "bertentangan" in str(error), error
            else:
                raise AssertionError("Stored lateness on a holiday snapshot was silently discarded.")
            with transaction() as (_, cursor):
                cursor.execute("DELETE FROM attendance_records WHERE student_id=%s AND attendance_date=%s",
                               (student_ids[0], start + timedelta(days=2)))

            # A missing stored status on a required date fails closed.
            with transaction() as (_, cursor):
                cursor.execute(
                    "DELETE FROM attendance_records WHERE student_id=%s AND attendance_date=%s",
                    (student_ids[0], end),
                )
            try:
                aggregate_period(
                    year_id=year_id, start_value=start.isoformat(), end_value=end.isoformat(), today=today,
                )
            except KMeansAggregationError as error:
                assert "Periode belum lengkap" in str(error), error
            else:
                raise AssertionError("Incomplete required attendance period was accepted.")
            print(
                "T27 MySQL smoke PASS: completed-year bounds, snapshot backfill/idempotency, "
                "immutable dates, holiday exclusion, manual formula, inactive student, "
                "zero denominator, incomplete period."
            )
        finally:
            with transaction() as (_, cursor):
                if class_id:
                    cursor.execute("DELETE FROM attendance_day_snapshots WHERE class_id=%s", (class_id,))
                if student_ids:
                    marks = ",".join(["%s"] * len(student_ids))
                    ids = tuple(student_ids)
                    cursor.execute(f"DELETE FROM attendance_records WHERE student_id IN ({marks})", ids)
                    cursor.execute(f"DELETE FROM student_class_enrollments WHERE student_id IN ({marks})", ids)
                    cursor.execute(f"DELETE FROM students WHERE id IN ({marks})", ids)
                if user_ids:
                    marks = ",".join(["%s"] * len(user_ids))
                    cursor.execute(f"DELETE FROM users WHERE id IN ({marks})", tuple(user_ids))
                if class_id:
                    cursor.execute("DELETE FROM schedule_exceptions WHERE class_id=%s", (class_id,))
                    cursor.execute("DELETE FROM classes WHERE id=%s", (class_id,))
                if year_id:
                    cursor.execute("DELETE FROM attendance_schedules WHERE academic_year_id=%s", (year_id,))
                    cursor.execute("DELETE FROM academic_years WHERE id=%s", (year_id,))
            print("cleanup=ok")


if __name__ == "__main__":
    main()
