"""Admin K-Means analysis pages are authorized and display stored run data (T29)."""

from __future__ import annotations

import unittest
from decimal import Decimal
from unittest.mock import ANY, patch

from app import create_app
from app.services.auth_service import credential_stamp
from app.services.kmeans_aggregation_service import KMeansAggregationError
from app.services.kmeans_run_service import KMeansRunError


class AdminKMeansRouteTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app({"TESTING": True, "SECRET_KEY": "admin-kmeans-test"})
        self.client = self.app.test_client()
        self.admin = {"id": 981, "username": "admin-kmeans", "password_hash": "hash",
                      "role": "admin", "is_active": 1, "must_change_password": 0}
        self.teacher = {**self.admin, "id": 982, "username": "teacher-kmeans", "role": "teacher"}

    def login(self, user):
        with self.app.app_context(), self.client.session_transaction() as session:
            session["user_id"] = user["id"]
            session["credential_stamp"] = credential_stamp(user["password_hash"])
            session["_csrf_token"] = "admin-kmeans-csrf"

    def active_user(self, user):
        return patch("app.services.auth_service.fetch_active_user", return_value=user)

    def test_analysis_and_run_detail_require_admin_on_direct_urls(self):
        self.login(self.teacher)
        with self.active_user(self.teacher):
            analysis = self.client.get("/admin/analytics")
            detail = self.client.get("/admin/analytics/runs/7")
        self.assertEqual(analysis.status_code, 403)
        self.assertEqual(detail.status_code, 403)

    def test_form_history_and_local_chart_are_available_to_admin(self):
        self.login(self.admin)
        years = [{"id": 6, "name": "2024/2025", "start_date": "2024-07-15",
                  "end_date": "2025-06-30"}]
        history = {"rows": [], "page": 1, "page_size": 25, "total": 0, "pages": 1}
        with self.active_user(self.admin), \
                patch("app.admin.routes.list_completed_academic_years", create=True,
                      return_value=years), \
                patch("app.admin.routes.list_analysis_runs", create=True,
                      return_value=history):
            response = self.client.get("/admin/analytics")
        self.assertEqual(response.status_code, 200)
        body = response.get_data(as_text=True)
        self.assertIn("Analisis K-Means", body)
        self.assertIn('name="submission_nonce"', body)
        self.assertIn('name="csrf_token"', body)
        self.assertIn("2024/2025", body)
        self.assertIn("Belum ada histori analisis", body)
        self.assertIn("/static/js/admin-kmeans.js", body)
        self.assertNotIn("cdn.jsdelivr.net", body)
        self.assertEqual(response.headers["Cache-Control"], "no-store")

    def test_invalid_or_incomplete_period_is_reported_without_creating_run(self):
        self.login(self.admin)
        with self.active_user(self.admin), \
                patch("app.admin.routes.list_completed_academic_years", create=True,
                      return_value=[]), \
                patch("app.admin.routes.list_analysis_runs", create=True,
                      return_value={"rows": [], "page": 1, "pages": 1, "total": 0}), \
                patch("app.admin.routes.create_analysis_run", create=True,
                      side_effect=KMeansAggregationError("Periode belum lengkap.")) as create:
            with self.client.session_transaction() as session:
                session["kmeans_submission_nonce"] = "one-use-token"
            response = self.client.post("/admin/analytics", data={
                "csrf_token": "admin-kmeans-csrf", "submission_nonce": "one-use-token",
                "academic_year_id": "6", "start_date": "2024-07-15", "end_date": "2025-06-30",
            })
        self.assertEqual(response.status_code, 302)
        create.assert_called_once_with(
            year_id=6, start_value="2024-07-15", end_value="2025-06-30", created_by=981,
            submission_key_hash=ANY,
        )
        with self.client.session_transaction() as session:
            self.assertNotIn("kmeans_submission_nonce", session)

    def test_one_use_form_nonce_blocks_duplicate_submit(self):
        self.login(self.admin)
        with self.active_user(self.admin), \
                patch("app.admin.routes.create_analysis_run", create=True,
                      return_value={"run_id": 71}) as create:
            with self.client.session_transaction() as session:
                session["kmeans_submission_nonce"] = "one-use-token"
            form = {"csrf_token": "admin-kmeans-csrf", "submission_nonce": "one-use-token",
                    "academic_year_id": "6", "start_date": "2024-07-15",
                    "end_date": "2025-06-30"}
            first = self.client.post("/admin/analytics", data=form)
            duplicate = self.client.post("/admin/analytics", data=form)
        self.assertEqual(first.status_code, 302)
        self.assertEqual(first.location, "/admin/analytics/runs/71")
        self.assertEqual(duplicate.status_code, 409)
        create.assert_called_once()

    def test_failed_persistence_is_safe_and_does_not_publish_a_run(self):
        self.login(self.admin)
        with self.active_user(self.admin), \
                patch("app.admin.routes.create_analysis_run", create=True,
                      side_effect=KMeansRunError("Hasil analisis gagal disimpan.")) as create, \
                patch("app.admin.routes.list_completed_academic_years", create=True,
                      return_value=[]), \
                patch("app.admin.routes.list_analysis_runs", create=True,
                      return_value={"rows": [], "page": 1, "pages": 1, "total": 0}):
            with self.client.session_transaction() as session:
                session["kmeans_submission_nonce"] = "one-use-token"
            response = self.client.post("/admin/analytics", data={
                "csrf_token": "admin-kmeans-csrf", "submission_nonce": "one-use-token",
                "academic_year_id": "6", "start_date": "2024-07-15", "end_date": "2025-06-30",
            })
        self.assertEqual(response.status_code, 302)
        self.assertIn("/admin/analytics?", response.location)
        create.assert_called_once()

    def test_saved_run_detail_uses_same_centroids_and_results_for_chart_and_table(self):
        self.login(self.admin)
        model = {
            "run": {"id": 71, "academic_year_name": "2024/2025", "period_start": "2024-08-01",
                    "period_end": "2025-05-30", "formula_version": "prd-attendance-v1",
                    "label_rule_version": "rank-v1", "random_state": 42, "n_init": 10,
                    "cluster_count": 3, "eligible_students": 3, "ineligible_students": 0,
                    "reconstructed_snapshot_dates": 2, "created_at": "2025-07-01 10:00"},
            "centroids": [{"cluster_no": 1, "cluster_label": "tinggi",
                           "attendance_percentage": 98.0, "late_count": Decimal("1.5000"),
                           "alpha_count": Decimal("0.2500"), "student_count": 4}],
            "results": [{"student_id": 1, "nisn": "001", "full_name": "Siswa Uji",
                         "class_name": "X-1", "attendance_percentage": 98.0,
                         "late_count": 0, "alpha_count": 0, "is_eligible": 1,
                         "cluster_no": 1, "cluster_label": "tinggi",
                         "reconstructed_days": 2}],
        }
        with self.active_user(self.admin), \
                patch("app.admin.routes.get_analysis_run", create=True,
                      return_value=model) as read:
            response = self.client.get("/admin/analytics/runs/71")
        self.assertEqual(response.status_code, 200)
        read.assert_called_once_with(71)
        body = response.get_data(as_text=True)
        self.assertIn("Siswa Uji", body)
        self.assertIn("tinggi", body)
        self.assertIn("2 tanggal memakai snapshot yang direkonstruksi", body)
        self.assertIn('id="kmeans-chart-data"', body)
        self.assertIn('"attendance_percentage": 98.0', body)
        self.assertIn('"late_count": 1.5', body)
        self.assertIn('"alpha_count": 0.25', body)
        self.assertIn("<td>1.5</td>", body)
        self.assertIn("<td>0.25</td>", body)
        self.assertIn("98.00%", body)

    def test_unknown_run_is_not_found(self):
        self.login(self.admin)
        with self.active_user(self.admin), \
                patch("app.admin.routes.get_analysis_run", create=True, return_value=None):
            response = self.client.get("/admin/analytics/runs/999")
        self.assertEqual(response.status_code, 404)

    def test_extreme_history_page_is_rejected_as_bad_request(self):
        self.login(self.admin)
        with self.active_user(self.admin):
            response = self.client.get("/admin/analytics?page=" + "9" * 5000)
        self.assertEqual(response.status_code, 400)


if __name__ == "__main__":
    unittest.main()
