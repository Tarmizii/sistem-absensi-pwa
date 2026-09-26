"""Teacher monitoring route boundaries and active navigation (T22)."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from app import create_app
from app.services.attendance_read_service import AttendanceReadError
from app.services.auth_service import credential_stamp
from pymysql import MySQLError


class TeacherMonitoringRouteTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app({"TESTING": True, "SECRET_KEY": "teacher-monitoring-test"})
        self.client = self.app.test_client()
        self.teacher = {"id": 503, "username": "teacher-monitor", "password_hash": "hash",
                        "role": "teacher", "is_active": 1, "must_change_password": 0}
        self.student = {"id": 504, "username": "student-monitor", "password_hash": "hash",
                        "role": "student", "is_active": 1, "must_change_password": 0,
                        "face_registered": 1}

    def login(self, user):
        with self.app.app_context(), self.client.session_transaction() as session:
            session["user_id"] = user["id"]
            session["credential_stamp"] = credential_stamp(user["password_hash"])
            session["_csrf_token"] = "monitoring-csrf"

    def test_teacher_dashboard_uses_assigned_read_model_and_shows_live_navigation(self):
        self.login(self.teacher)
        model = {"classes": [], "selected_class": None, "today": "2026-09-24",
                 "server_time": "07:00", "summary": {}}
        with patch("app.services.auth_service.fetch_active_user", return_value=self.teacher), \
                patch("app.role_routes.get_teacher_dashboard", return_value=model) as read:
            response = self.client.get("/teacher/dashboard?class_id=17")
        self.assertEqual(response.status_code, 200)
        read.assert_called_once_with(self.teacher["id"], "17")
        body = response.get_data(as_text=True)
        self.assertIn('aria-current="page"', body)
        self.assertIn('href="/teacher/attendance"', body)
        self.assertIn('href="/teacher/students"', body)

    def test_all_monitoring_routes_require_teacher_role(self):
        self.login(self.student)
        with patch("app.services.auth_service.fetch_active_user", return_value=self.student):
            for path in ("/teacher/attendance", "/teacher/students", "/teacher/students/9"):
                with self.subTest(path=path):
                    self.assertEqual(self.client.get(path).status_code, 403)

    def test_assigned_class_outside_scope_returns_not_found(self):
        self.login(self.teacher)
        with patch("app.services.auth_service.fetch_active_user", return_value=self.teacher), \
                patch("app.teacher.routes.get_teacher_students",
                      side_effect=AttendanceReadError("Kelas tidak ditemukan.", 404)):
            response = self.client.get("/teacher/students?class_id=9999")
        self.assertEqual(response.status_code, 404)

    def test_invalid_filter_returns_bad_request(self):
        self.login(self.teacher)
        with patch("app.services.auth_service.fetch_active_user", return_value=self.teacher), \
                patch("app.teacher.routes.get_teacher_attendance",
                      side_effect=AttendanceReadError("Filter status tidak valid.", 400)):
            response = self.client.get("/teacher/attendance?status=unknown")
        self.assertEqual(response.status_code, 400)

    def test_detail_database_error_keeps_retry_destination(self):
        self.login(self.teacher)
        with patch("app.services.auth_service.fetch_active_user", return_value=self.teacher), \
                patch("app.teacher.routes.get_teacher_student_detail",
                      side_effect=MySQLError("database unavailable")):
            response = self.client.get("/teacher/students/9?class_id=12&month=2026-09")
        self.assertEqual(response.status_code, 503)
        self.assertIn("/teacher/students/9?", response.get_data(as_text=True))


if __name__ == "__main__":
    unittest.main()
