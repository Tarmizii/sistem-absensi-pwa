"""Verify T28 K-Means persistence, history, and transaction rollback on dev MySQL."""

from __future__ import annotations

from contextlib import contextmanager
from datetime import date, timedelta
from unittest.mock import patch
import secrets

from werkzeug.security import generate_password_hash

from app import create_app
from app.database import get_db, transaction
from app.services.kmeans_run_service import (
    KMeansRunError,
    create_analysis_run,
    get_analysis_run,
)


def main() -> None:
    app = create_app({"TESTING": True})
    if app.config["APP_ENV"] == "production":
        raise SystemExit("Smoke T28 hanya boleh memakai database development/test.")
    suffix = secrets.token_hex(4)
    start = date(2025, 8, 1)
    end = date(2025, 8, 3)
    today = date(2026, 9, 24)
    password_hash = generate_password_hash(f"Smoke-T28-{suffix}-temporary-password")
    user_ids: list[int] = []
    student_ids: list[int] = []
    run_ids: list[int] = []
    year_id = class_id = None

    with app.app_context():
        try:
            with transaction() as (_, cursor):
                cursor.execute(
                    """INSERT INTO users (username,password_hash,role,is_active,must_change_password)
                       VALUES (%s,%s,'admin',1,0)""",
                    (f"smoke-t28-admin-{suffix}", password_hash),
                )
                admin_id = int(cursor.lastrowid)
                user_ids.append(admin_id)
                cursor.execute(
                    """INSERT INTO academic_years (name,start_date,end_date,is_active)
                       VALUES (%s,%s,%s,0)""",
                    (f"T28-{suffix}", start, end),
                )
                year_id = int(cursor.lastrowid)
                cursor.execute(
                    "INSERT INTO classes (academic_year_id,name,is_active) VALUES (%s,%s,1)",
                    (year_id, f"X-T28-{suffix}"),
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
                for day_index in range(3):
                    cursor.execute(
                        """INSERT INTO attendance_day_snapshots
                           (academic_year_id,class_id,attendance_date,requires_attendance,source)
                           VALUES (%s,%s,%s,1,'reconstructed')""",
                        (year_id, class_id, start + timedelta(days=day_index)),
                    )

                statuses = (
                    ("satu", 1, ("present", "present", "late")),
                    ("dua", 1, ("present", "absent", "present")),
                    ("tiga", 0, ("absent", "absent", "late")),
                    ("nol-efektif", 1, ("permit", "sick", "permit")),
                )
                for label, active, day_statuses in statuses:
                    cursor.execute(
                        """INSERT INTO users
                           (username,password_hash,role,is_active,must_change_password)
                           VALUES (%s,%s,'student',%s,0)""",
                        (f"smoke-t28-{label}-{suffix}", password_hash, active),
                    )
                    user_id = int(cursor.lastrowid)
                    user_ids.append(user_id)
                    cursor.execute(
                        """INSERT INTO students (user_id,nisn,full_name,face_registered)
                           VALUES (%s,%s,%s,1)""",
                        (user_id, f"T28{suffix}{len(student_ids):02d}", f"T28 {label} {suffix}"),
                    )
                    student_id = int(cursor.lastrowid)
                    student_ids.append(student_id)
                    cursor.execute(
                        """INSERT INTO student_class_enrollments
                           (student_id,academic_year_id,class_id) VALUES (%s,%s,%s)""",
                        (student_id, year_id, class_id),
                    )
                    for day_index, status in enumerate(day_statuses):
                        cursor.execute(
                            """INSERT INTO attendance_records
                               (student_id,class_id,attendance_date,status,status_source)
                               VALUES (%s,%s,%s,%s,'teacher')""",
                            (student_id, class_id, start + timedelta(days=day_index), status),
                        )

            first = create_analysis_run(
                year_id=year_id, start_value=start.isoformat(), end_value=end.isoformat(),
                created_by=admin_id, today=today,
            )
            run_ids.append(first["run_id"])
            second = create_analysis_run(
                year_id=year_id, start_value=start.isoformat(), end_value=end.isoformat(),
                created_by=admin_id, today=today,
            )
            run_ids.append(second["run_id"])
            assert first["run_id"] != second["run_id"]
            assert first["eligible_students"] == 3 and first["ineligible_students"] == 1, first
            assert [center["label"] for center in first["centroids"]] == [
                "tinggi", "sedang", "rendah"
            ], first

            def result_projection(run_id: int):
                saved = get_analysis_run(run_id)
                assert saved is not None
                return {
                    row["student_id"]: (row["cluster_no"], row["cluster_label"],
                                        row["attendance_percentage"], row["late_count"],
                                        row["alpha_count"], row["is_eligible"])
                    for row in saved["results"]
                }

            first_saved = get_analysis_run(first["run_id"])
            second_saved = get_analysis_run(second["run_id"])
            assert first_saved is not None and second_saved is not None
            assert first_saved["run"]["formula_version"] == "prd-attendance-v1"
            assert first_saved["run"]["label_rule_version"]
            assert int(first_saved["run"]["random_state"]) == 42
            assert len(first_saved["centroids"]) == 3
            assert result_projection(first["run_id"]) == result_projection(second["run_id"])
            assert first_saved["run"]["reconstructed_snapshot_dates"] == 3

            # Raise after one result INSERT; the enclosing real transaction must roll back the run.
            original_transaction = transaction

            @contextmanager
            def failing_transaction():
                with original_transaction() as (connection, real_cursor):
                    class CursorProxy:
                        failed = False

                        def execute(self, query, params=None):
                            result = real_cursor.execute(query, params)
                            if (not self.failed
                                    and query.lstrip().startswith("INSERT INTO kmeans_results")):
                                self.failed = True
                                raise RuntimeError("synthetic failure after first result row")
                            return result

                        def __getattr__(self, name):
                            return getattr(real_cursor, name)

                    yield connection, CursorProxy()

            with get_db().cursor() as cursor:
                cursor.execute("SELECT COUNT(*) AS total FROM kmeans_runs WHERE academic_year_id=%s", (year_id,))
                before_rollback = int(cursor.fetchone()["total"])
            with patch("app.services.kmeans_run_service.transaction", failing_transaction):
                try:
                    create_analysis_run(
                        year_id=year_id, start_value=start.isoformat(), end_value=end.isoformat(),
                        created_by=admin_id, today=today,
                    )
                except KMeansRunError as error:
                    assert "Tidak ada run parsial" in str(error), error
                else:
                    raise AssertionError("Injected K-Means storage failure was accepted.")
            with get_db().cursor() as cursor:
                cursor.execute("SELECT COUNT(*) AS total FROM kmeans_runs WHERE academic_year_id=%s", (year_id,))
                assert int(cursor.fetchone()["total"]) == before_rollback

            print(
                "T28 MySQL smoke PASS: three labelled centroids, inactive student, "
                "ineligible denominator, repeated historical runs, immutable run 1, "
                "metadata/features/centroids stored, transaction rollback."
            )
        finally:
            with transaction() as (_, cursor):
                if run_ids:
                    marks = ",".join(["%s"] * len(run_ids))
                    ids = tuple(run_ids)
                    cursor.execute(f"DELETE FROM kmeans_results WHERE run_id IN ({marks})", ids)
                    cursor.execute(f"DELETE FROM kmeans_centroids WHERE run_id IN ({marks})", ids)
                    cursor.execute(f"DELETE FROM kmeans_runs WHERE id IN ({marks})", ids)
                if year_id:
                    cursor.execute("DELETE FROM kmeans_results WHERE run_id IN (SELECT id FROM kmeans_runs WHERE academic_year_id=%s)", (year_id,))
                    cursor.execute("DELETE FROM kmeans_centroids WHERE run_id IN (SELECT id FROM kmeans_runs WHERE academic_year_id=%s)", (year_id,))
                    cursor.execute("DELETE FROM kmeans_runs WHERE academic_year_id=%s", (year_id,))
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
                    cursor.execute("DELETE FROM classes WHERE id=%s", (class_id,))
                if year_id:
                    cursor.execute("DELETE FROM attendance_schedules WHERE academic_year_id=%s", (year_id,))
                    cursor.execute("DELETE FROM academic_years WHERE id=%s", (year_id,))
            print("cleanup=ok")


if __name__ == "__main__":
    main()
