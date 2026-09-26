"""Admin attendance monitoring route contract (T25)."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from app import create_app
from app.services.attendance_read_service import AttendanceReadError
from app.services.auth_service import credential_stamp
from pymysql import MySQLError


class AdminAttendanceRouteTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app({"TESTING": True, "SECRET_KEY": "admin-attendance-test"})
        self.client = self.app.test_client()
        self.admin = {"id": 931, "username": "admin-monitor", "password_hash": "hash",
                      "role": "admin", "is_active": 1, "must_change_password": 0}
        self.teacher = {**self.admin, "id": 932, "username": "teacher-monitor",
                        "role": "teacher"}
        self.student = {**self.admin, "id": 933, "username": "student-monitor",
                        "role": "student", "face_registered": 1}

    def login(self, user):
        with self.app.app_context(), self.client.session_transaction() as session:
            session["user_id"] = user["id"]
            session["credential_stamp"] = credential_stamp(user["password_hash"])
            session["_csrf_token"] = "admin-monitor-csrf"

    def active_user(self, user):
        return patch("app.services.auth_service.fetch_active_user", return_value=user)

    def test_journal_requires_admin_even_when_opened_by_direct_url(self):
        for user in (self.teacher, self.student):
            with self.subTest(role=user["role"]):
                self.login(user)
                with self.active_user(user):
                    response = self.client.get("/admin/attendance")
                self.assertEqual(response.status_code, 403)

    def test_journal_passes_validated_filter_values_to_read_model(self):
        self.login(self.admin)
        model = {
            "date": "2026-09-24", "classes": [], "selected_class_id": 8,
            "summary": {"total": 41, "present": 22, "late": 3, "permit": 1,
                        "sick": 1, "absent": 2, "pending": 12},
            "rows": [{"record_id": 901, "date": "2026-09-24", "class_name": "X-1",
                      "student_id": 902, "full_name": "Rani Uji", "nisn": "0012345678",
                      "status": "present", "status_label": "Hadir", "notes": None,
                      "checkin_time": "07:00", "checkout_time": "15:00"}],
            "page": 2, "pages": 3, "total": 51,
            "status": "", "q": "", "class_id": "8", "is_today": True,
            "school_day": True,
        }
        with self.active_user(self.admin), \
                patch("app.admin.routes.get_admin_attendance", create=True,
                      return_value=model) as read:
            response = self.client.get(
                "/admin/attendance?date=2026-09-24&class_id=8&status=&q=&page=2"
            )
        self.assertEqual(response.status_code, 200)
        read.assert_called_once_with("2026-09-24", "8", "", "", "2")
        self.assertEqual(response.headers["Cache-Control"], "no-store")
        body = response.get_data(as_text=True)
        self.assertIn("Monitoring presensi", body)
        self.assertIn("41", body)
        self.assertIn("Halaman 2 dari 3", body)

    def test_invalid_filter_is_rejected_as_bad_request(self):
        self.login(self.admin)
        with self.active_user(self.admin), \
                patch("app.admin.routes.get_admin_attendance", create=True,
                      side_effect=AttendanceReadError("Tanggal tidak valid.", 400)):
            response = self.client.get("/admin/attendance?date=not-a-date")
        self.assertEqual(response.status_code, 400)

    def test_database_failure_has_retryable_error_state_and_preserves_filters(self):
        self.login(self.admin)
        with self.active_user(self.admin), \
                patch("app.admin.routes.get_admin_attendance", create=True,
                      side_effect=MySQLError("database unavailable")):
            response = self.client.get("/admin/attendance?date=2026-09-24&class_id=8&q=Rani")
        self.assertEqual(response.status_code, 503)
        self.assertIn("Coba muat ulang", response.get_data(as_text=True))
        self.assertIn("date=2026-09-24", response.get_data(as_text=True))
        self.assertEqual(response.headers["Cache-Control"], "no-store")

    def test_student_detail_uses_admin_month_history_and_links_evidence(self):
        self.login(self.admin)
        student = {"student_id": 141, "nisn": "0012345678", "full_name": "Rani Uji",
                   "is_active": 1, "face_registered": 1, "must_change_password": 0}
        history = [{"record_id": 901, "date": "2026-09-02", "status_label": "Hadir",
                    "checkin_time": "07:01", "checkout_time": "15:02",
                    "class_name": "X-1"}]
        with self.active_user(self.admin), \
                patch("app.admin.routes.get_student", return_value=student), \
                patch("app.admin.routes.get_admin_student_month_history", create=True,
                      return_value=history) as read:
            response = self.client.get("/admin/students/141?month=2026-09")
        self.assertEqual(response.status_code, 200)
        read.assert_called_once_with(141, "2026-09")
        body = response.get_data(as_text=True)
        self.assertIn("Histori presensi bulanan", body)
        self.assertIn("/attendance/901/evidence", body)
        self.assertIn("2026-09", body)


if __name__ == "__main__":
    unittest.main()
