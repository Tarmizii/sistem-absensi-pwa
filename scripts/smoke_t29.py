"""Verify the Admin K-Means form, idempotent submission, and saved-run page on dev MySQL."""

from __future__ import annotations

from datetime import date, timedelta
import hashlib
import re
import secrets

from werkzeug.security import generate_password_hash

from app import create_app
from app.database import get_db, transaction
from app.services.auth_service import credential_stamp
from app.services.kmeans_run_service import create_analysis_run, get_analysis_run
from unittest.mock import patch


def main() -> None:
    app = create_app({"TESTING": True, "SECRET_KEY": "smoke-t29"})
    if app.config["APP_ENV"] == "production":
        raise SystemExit("Smoke T29 hanya boleh memakai database development/test.")
    suffix = secrets.token_hex(4)
    start, end, today = date(2025, 8, 1), date(2025, 8, 3), date(2026, 9, 24)
    password_hash = generate_password_hash(f"Smoke-T29-{suffix}-temporary-password")
    year_id = class_id = admin_id = None
    user_ids: list[int] = []
    student_ids: list[int] = []
    run_ids: list[int] = []
    submission_hash = hashlib.sha256(f"smoke-t29-{suffix}".encode("ascii")).hexdigest()

    with app.app_context():
        try:
            with transaction() as (_, cursor):
                cursor.execute(
                    """INSERT INTO users (username,password_hash,role,is_active,must_change_password)
                       VALUES (%s,%s,'admin',1,0)""",
                    (f"smoke-t29-admin-{suffix}", password_hash),
                )
                admin_id = int(cursor.lastrowid)
                user_ids.append(admin_id)
                cursor.execute(
                    "INSERT INTO academic_years (name,start_date,end_date,is_active) VALUES (%s,%s,%s,0)",
                    (f"T29-{suffix}", start, end),
                )
                year_id = int(cursor.lastrowid)
                cursor.execute(
                    "INSERT INTO classes (academic_year_id,name,is_active) VALUES (%s,%s,1)",
                    (year_id, f"X-T29-{suffix}"),
                )
                class_id = int(cursor.lastrowid)
                for weekday in range(1, 8):
                    cursor.execute(
                        """INSERT INTO attendance_schedules
                           (academic_year_id,day_of_week,checkin_start,late_after,checkin_cutoff,
                            checkout_start,is_active) VALUES (%s,%s,'06:30','07:15','08:00','15:00',1)""",
                        (year_id, weekday),
                    )
                for day_index in range(3):
                    cursor.execute(
                        """INSERT INTO attendance_day_snapshots
                           (academic_year_id,class_id,attendance_date,requires_attendance,source)
                           VALUES (%s,%s,%s,1,'reconstructed')""",
                        (year_id, class_id, start + timedelta(days=day_index)),
                    )
                profiles = (
                    ("A", ("present", "present", "late")),
                    ("B", ("present", "absent", "present")),
                    ("C", ("absent", "absent", "late")),
                )
                for label, statuses in profiles:
                    cursor.execute(
                        """INSERT INTO users
                           (username,password_hash,role,is_active,must_change_password)
                           VALUES (%s,%s,'student',1,0)""",
                        (f"smoke-t29-student-{label}-{suffix}", password_hash),
                    )
                    user_id = int(cursor.lastrowid)
                    user_ids.append(user_id)
                    cursor.execute(
                        "INSERT INTO students (user_id,nisn,full_name,face_registered) VALUES (%s,%s,%s,1)",
                        (user_id, f"T29{suffix}{len(student_ids):02d}", f"T29 Siswa {label} {suffix}"),
                    )
                    student_id = int(cursor.lastrowid)
                    student_ids.append(student_id)
                    cursor.execute(
                        """INSERT INTO student_class_enrollments (student_id,academic_year_id,class_id)
                           VALUES (%s,%s,%s)""",
                        (student_id, year_id, class_id),
                    )
                    for day_index, status in enumerate(statuses):
                        cursor.execute(
                            """INSERT INTO attendance_records
                               (student_id,class_id,attendance_date,status,status_source)
                               VALUES (%s,%s,%s,%s,'teacher')""",
                            (student_id, class_id, start + timedelta(days=day_index), status),
                        )

            user = {"id": admin_id, "username": f"smoke-t29-admin-{suffix}",
                    "password_hash": password_hash, "role": "admin", "is_active": 1,
                    "must_change_password": 0}
            client = app.test_client()
            with client.session_transaction() as session:
                session["user_id"] = admin_id
                session["credential_stamp"] = credential_stamp(password_hash)
                session["_csrf_token"] = "smoke-t29-csrf"
            with patch("app.services.auth_service.fetch_active_user", return_value=user):
                form_page = client.get("/admin/analytics")
                assert form_page.status_code == 200, form_page.status_code
                html = form_page.get_data(as_text=True)
                assert f"T29-{suffix}" in html
                nonce_match = re.search(r'name="submission_nonce" value="([^"]+)"', html)
                assert nonce_match, "one-use form key missing"
                nonce = nonce_match.group(1)
                post = client.post("/admin/analytics", data={
                    "csrf_token": "smoke-t29-csrf", "submission_nonce": nonce,
                    "academic_year_id": str(year_id), "start_date": start.isoformat(),
                    "end_date": end.isoformat(),
                })
                assert post.status_code == 302, post.status_code
                run_id = int(post.location.rstrip("/").split("/")[-1])
                run_ids.append(run_id)
                assert post.location.endswith(f"/admin/analytics/runs/{run_id}")
                repeated = client.post("/admin/analytics", data={
                    "csrf_token": "smoke-t29-csrf", "submission_nonce": nonce,
                    "academic_year_id": str(year_id), "start_date": start.isoformat(),
                    "end_date": end.isoformat(),
                })
                assert repeated.status_code == 409
                detail = client.get(post.location)
                assert detail.status_code == 200, detail.status_code
                detail_html = detail.get_data(as_text=True)
                assert "T29 Siswa" in detail_html
                assert "kmeans-chart-data" in detail_html
                assert "/static/js/vendor/chart.umd.min.js" in detail_html
                assert "cdn.jsdelivr.net" not in detail_html

            duplicate = create_analysis_run(
                year_id=year_id, start_value=start.isoformat(), end_value=end.isoformat(),
                created_by=admin_id, today=today, submission_key_hash=hashlib.sha256(
                    nonce.encode("ascii")).hexdigest(),
            )
            assert duplicate["run_id"] == run_id and duplicate["duplicate"] is True, duplicate
            saved = get_analysis_run(run_id)
            assert saved is not None and len(saved["centroids"]) == 3
            assert len(saved["results"]) == 3
            with get_db().cursor() as cursor:
                cursor.execute("SELECT COUNT(*) AS total FROM kmeans_runs WHERE submission_key_hash=%s",
                               (hashlib.sha256(nonce.encode("ascii")).hexdigest(),))
                assert int(cursor.fetchone()["total"]) == 1
            print("T29 MySQL smoke PASS: ended-year selector, Admin form, one-use submit, saved detail, local chart payload, duplicate DB key.")
        finally:
            with transaction() as (_, cursor):
                if run_ids:
                    marks = ",".join(["%s"] * len(run_ids))
                    ids = tuple(run_ids)
                    cursor.execute(f"DELETE FROM kmeans_results WHERE run_id IN ({marks})", ids)
                    cursor.execute(f"DELETE FROM kmeans_centroids WHERE run_id IN ({marks})", ids)
                    cursor.execute(f"DELETE FROM kmeans_runs WHERE id IN ({marks})", ids)
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
