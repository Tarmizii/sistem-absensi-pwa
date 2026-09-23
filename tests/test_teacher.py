"""T08 Teacher management route and validation tests."""

from __future__ import annotations

import re
import unittest
from unittest.mock import patch

from werkzeug.security import generate_password_hash

from app import create_app
from app.services.auth_service import credential_stamp
from app.services.teacher_service import TeacherValidationError, validate_teacher_input


ADMIN = {"id": 18, "username": "admin", "password_hash": generate_password_hash("synthetic-admin"),
         "role": "admin", "is_active": 1, "must_change_password": 0}
TEACHER = {"id": 19, "username": "teacher.test", "password_hash": generate_password_hash("synthetic-teacher"),
           "role": "teacher", "is_active": 1, "must_change_password": 0}


class TeacherManagementTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app({"TESTING": True, "SECRET_KEY": "teacher-test"})
        self.client = self.app.test_client()

    def as_user(self, user):
        with self.app.app_context(), self.client.session_transaction() as session:
            session["user_id"] = user["id"]
            session["credential_stamp"] = credential_stamp(user["password_hash"])

    def token(self, path):
        response = self.client.get(path)
        match = re.search(r'name="csrf_token" value="([^"]+)"', response.get_data(as_text=True))
        self.assertIsNotNone(match)
        return match.group(1)

    def test_teacher_input_is_normalized_and_invalid_values_rejected(self):
        self.assertEqual(validate_teacher_input("  guru.01 ", "  Siti   Aminah ", "  198001  "),
                         ("guru.01", "Siti Aminah", "198001"))
        for args in (("bad username!", "Siti Aminah", ""), ("guru", "A", ""),
                     ("guru", "Siti Aminah", "x"), ("guru", "Siti\nAminah", "")):
            with self.subTest(args=args), self.assertRaises(TeacherValidationError):
                validate_teacher_input(*args)

    def test_non_admin_cannot_open_teacher_management(self):
        self.as_user(TEACHER)
        with patch("app.services.auth_service.fetch_active_user", return_value=TEACHER):
            response = self.client.get("/admin/teachers")
        self.assertEqual(response.status_code, 403)

    def test_admin_list_search_and_navigation_render(self):
        self.as_user(ADMIN)
        rows = [{"teacher_id": 4, "user_id": 44, "full_name": "Siti Aminah",
                 "employee_number": "198001", "username": "siti.aminah",
                 "is_active": 1, "must_change_password": 1}]
        with patch("app.services.auth_service.fetch_active_user", return_value=ADMIN), \
                patch("app.admin.routes.list_teachers", return_value=rows) as list_mock:
            response = self.client.get("/admin/teachers?q=siti")
        self.assertEqual(response.status_code, 200)
        self.assertIn("Siti Aminah", response.get_data(as_text=True))
        self.assertIn("/admin/teachers/4", response.get_data(as_text=True))
        list_mock.assert_called_once_with("siti")

    def test_admin_can_create_and_receive_one_time_password(self):
        self.as_user(ADMIN)
        created = {"teacher_id": 5, "user_id": 45, "username": "guru.baru",
                   "full_name": "Guru Baru", "temporary_password": "temporary-only"}
        with patch("app.services.auth_service.fetch_active_user", return_value=ADMIN):
            token = self.token("/admin/teachers/new")
            with patch("app.admin.routes.create_teacher", return_value=created) as create_mock:
                response = self.client.post("/admin/teachers/new", data={
                    "csrf_token": token, "username": "guru.baru",
                    "full_name": "Guru Baru", "employee_number": "200001",
                })
        self.assertEqual(response.status_code, 200)
        body = response.get_data(as_text=True)
        self.assertIn("temporary-only", body)
        create_mock.assert_called_once_with(actor_user_id=18, username="guru.baru",
                                             full_name="Guru Baru", employee_number="200001")

    def test_service_errors_are_shown_without_redirecting_to_success(self):
        self.as_user(ADMIN)
        with patch("app.services.auth_service.fetch_active_user", return_value=ADMIN):
            token = self.token("/admin/teachers/new")
            with patch("app.admin.routes.create_teacher", side_effect=TeacherValidationError("Username sudah digunakan.")):
                response = self.client.post("/admin/teachers/new", data={
                    "csrf_token": token, "username": "guru.baru", "full_name": "Guru Baru",
                })
        self.assertEqual(response.status_code, 200)
        self.assertIn("Username sudah digunakan", response.get_data(as_text=True))
