"""Persist and read immutable K-Means runs (T28)."""

from __future__ import annotations

from datetime import date
import re
from typing import Any

from flask import current_app
from pymysql import IntegrityError

from app.database import get_db, transaction
from app.services.kmeans_aggregation_service import aggregate_period
from app.services.kmeans_clustering_service import (
    CLUSTER_COUNT,
    FORMULA_VERSION,
    LABEL_RULE_VERSION,
    N_INIT,
    RANDOM_STATE,
    cluster_students,
)


PAGE_SIZE = 25


class KMeansRunError(ValueError):
    """A run cannot be safely computed or stored."""


SUBMISSION_KEY_PATTERN = re.compile(r"^[0-9a-f]{64}$")


def create_analysis_run(*, year_id: int, start_value: Any, end_value: Any,
                        created_by: int, today: date | None = None,
                        submission_key_hash: str | None = None) -> dict[str, Any]:
    """Compute first, then store metadata, student rows, and centroids atomically."""

    if (not isinstance(created_by, int) or isinstance(created_by, bool)
            or created_by <= 0):
        raise KMeansRunError("Akun Admin untuk analisis tidak valid.")
    if submission_key_hash is not None and (
        not isinstance(submission_key_hash, str)
        or not SUBMISSION_KEY_PATTERN.fullmatch(submission_key_hash)
    ):
        raise KMeansRunError("Kunci pengiriman analisis tidak valid.")
    aggregation = aggregate_period(
        year_id=year_id, start_value=start_value, end_value=end_value, today=today,
    )
    clustered = cluster_students(aggregation["students"])
    assignment_by_student = clustered["assignments"]
    ineligible_count = int(aggregation["ineligible_students"])

    try:
        with transaction() as (_, cursor):
            cursor.execute(
                """INSERT INTO kmeans_runs
                   (academic_year_id,period_start,period_end,created_by,submission_key_hash,formula_version,
                    label_rule_version,random_state,n_init,cluster_count,eligible_students,
                    ineligible_students,reconstructed_snapshot_dates)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                (year_id, aggregation["start_date"], aggregation["end_date"], created_by,
                 submission_key_hash,
                 clustered["formula_version"], clustered["label_rule_version"],
                 clustered["random_state"], clustered["n_init"], CLUSTER_COUNT,
                 clustered["eligible_count"], ineligible_count,
                 aggregation["reconstructed_snapshot_dates"]),
            )
            run_id = int(cursor.lastrowid)

            for student in aggregation["students"]:
                assignment = assignment_by_student.get(int(student["student_id"]))
                cursor.execute(
                    """INSERT INTO kmeans_results
                       (run_id,student_id,class_id,attendance_percentage,late_count,alpha_count,
                        scheduled_school_days,effective_days,is_eligible,ineligible_reason,
                        reconstructed_days,cluster_no,cluster_label)
                       VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                    (run_id, int(student["student_id"]), int(student["class_id"]),
                     student["attendance_percentage"], int(student["late_count"]),
                     int(student["alpha_count"]), int(student["scheduled_school_days"]),
                     int(student["effective_days"]), int(bool(student["eligible"])),
                     student["ineligible_reason"], int(student["reconstructed_days"]),
                     assignment["cluster_no"] if assignment else None,
                     assignment["label"] if assignment else None),
                )

            for centroid in clustered["centroids"]:
                cursor.execute(
                    """INSERT INTO kmeans_centroids
                       (run_id,cluster_no,cluster_label,attendance_percentage,late_count,
                        alpha_count,student_count)
                       VALUES (%s,%s,%s,%s,%s,%s,%s)""",
                    (run_id, centroid["cluster_no"], centroid["label"],
                     centroid["attendance_percentage"], centroid["late_count"],
                     centroid["alpha_count"], centroid["student_count"]),
                )
    except IntegrityError as error:
        if submission_key_hash and "uq_kmeans_runs_submission_key" in str(error):
            with get_db().cursor() as cursor:
                cursor.execute(
                    "SELECT id FROM kmeans_runs WHERE submission_key_hash=%s AND created_by=%s LIMIT 1",
                    (submission_key_hash, created_by),
                )
                existing = cursor.fetchone()
            if existing:
                return {"run_id": int(existing["id"]), "duplicate": True}
        current_app.logger.exception(
            "kmeans.run_persist_failed year_id=%s start=%s end=%s",
            year_id, start_value, end_value,
        )
        raise KMeansRunError("Hasil analisis gagal disimpan. Tidak ada run parsial yang dicatat.") from None
    except Exception:
        current_app.logger.exception(
            "kmeans.run_persist_failed year_id=%s start=%s end=%s",
            year_id, start_value, end_value,
        )
        raise KMeansRunError("Hasil analisis gagal disimpan. Tidak ada run parsial yang dicatat.") from None

    return {
        "run_id": run_id,
        "academic_year_id": year_id,
        "academic_year_name": aggregation["academic_year_name"],
        "start_date": aggregation["start_date"],
        "end_date": aggregation["end_date"],
        "eligible_students": clustered["eligible_count"],
        "ineligible_students": ineligible_count,
        "reconstructed_snapshot_dates": aggregation["reconstructed_snapshot_dates"],
        "centroids": clustered["centroids"],
    }


def list_completed_academic_years(*, today: date | None = None) -> list[dict[str, Any]]:
    """List ended academic years that can be selected for a retrospective run."""

    if today is None:
        from app.services.schedule_service import application_now
        today = application_now().date()
    with get_db().cursor() as cursor:
        cursor.execute(
            """SELECT id,name,start_date,end_date
               FROM academic_years WHERE end_date < %s
               ORDER BY start_date DESC,id DESC LIMIT 100""",
            (today,),
        )
        return list(cursor.fetchall())


def list_analysis_runs(*, page: int = 1) -> dict[str, Any]:
    if not isinstance(page, int) or isinstance(page, bool) or page < 1:
        raise KMeansRunError("Halaman histori analisis tidak valid.")
    offset = (page - 1) * PAGE_SIZE
    with get_db().cursor() as cursor:
        cursor.execute("SELECT COUNT(*) AS total FROM kmeans_runs")
        total = int(cursor.fetchone()["total"])
        cursor.execute(
            """SELECT r.id,r.academic_year_id,ay.name AS academic_year_name,
                      r.period_start,r.period_end,r.eligible_students,r.ineligible_students,
                      r.reconstructed_snapshot_dates,r.created_at,u.username AS created_by
               FROM kmeans_runs AS r
               JOIN academic_years AS ay ON ay.id=r.academic_year_id
               JOIN users AS u ON u.id=r.created_by
               ORDER BY r.created_at DESC,r.id DESC LIMIT %s OFFSET %s""",
            (PAGE_SIZE, offset),
        )
        rows = list(cursor.fetchall())
    return {
        "rows": rows,
        "page": page,
        "page_size": PAGE_SIZE,
        "total": total,
        "pages": max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE),
    }


def get_analysis_run(run_id: int) -> dict[str, Any] | None:
    if not isinstance(run_id, int) or isinstance(run_id, bool) or run_id <= 0:
        raise KMeansRunError("ID run analisis tidak valid.")
    db = get_db()
    with db.cursor() as cursor:
        cursor.execute(
            """SELECT r.id,r.academic_year_id,ay.name AS academic_year_name,
                      r.period_start,r.period_end,r.created_by,u.username AS creator_username,
                      r.formula_version,r.label_rule_version,r.random_state,r.n_init,
                      r.cluster_count,r.eligible_students,r.ineligible_students,
                      r.reconstructed_snapshot_dates,r.created_at
               FROM kmeans_runs AS r
               JOIN academic_years AS ay ON ay.id=r.academic_year_id
               JOIN users AS u ON u.id=r.created_by
               WHERE r.id=%s LIMIT 1""",
            (run_id,),
        )
        run = cursor.fetchone()
        if run is None:
            return None
        cursor.execute(
            """SELECT cluster_no,cluster_label,attendance_percentage,late_count,alpha_count,
                      student_count
               FROM kmeans_centroids WHERE run_id=%s ORDER BY cluster_no""",
            (run_id,),
        )
        centroids = list(cursor.fetchall())
        cursor.execute(
            """SELECT r.student_id,s.nisn,s.full_name,r.class_id,c.name AS class_name,
                      r.attendance_percentage,r.late_count,r.alpha_count,
                      r.scheduled_school_days,r.effective_days,r.is_eligible,
                      r.ineligible_reason,r.reconstructed_days,r.cluster_no,r.cluster_label
               FROM kmeans_results AS r
               JOIN students AS s ON s.id=r.student_id
               JOIN classes AS c ON c.id=r.class_id
               WHERE r.run_id=%s
               ORDER BY r.cluster_no IS NULL,r.cluster_no,c.name,s.full_name,r.student_id""",
            (run_id,),
        )
        results = list(cursor.fetchall())
    return {"run": run, "centroids": centroids, "results": results}
