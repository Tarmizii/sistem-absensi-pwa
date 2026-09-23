"""T09 Student management route and validation tests."""

from __future__ import annotations

import re
import unittest
from unittest.mock import patch

from werkzeug.security import generate_password_hash

from app import create_app
from app.services.auth_service import credential_stamp
from app.services.student_service import StudentValidationError, validate_student_input


ADMIN = {"id": 18, "username": "admin", "password_hash": generate_password_hash("synthetic-admin"),
         "role": "admin", "is_active": 1, "must_change_password": 0}
TEACHER = {"id": 19, "username": "teacher.test", "password_hash": generate_password_hash("synthetic-teacher"),
           "role": "teacher", "is_active": 1, "must_change_password": 0}


class StudentManagementTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app({"TESTING": True, "SECRET_KEY": "student-test"})
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

    def test_student_input_preserves_leading_zero_and_rejects_invalid_values(self):
        self.assertEqual(validate_student_input(" 001234 ", "  Siti   Aminah "), ("001234", "Siti Aminah"))
        for args in (("12x4", "Siti Aminah"), ("123", "Siti Aminah"),
                     ("1" * 21, "Siti Aminah"), ("1234", "A"), ("1234", "Siti\nAminah")):
            with self.subTest(args=args), self.assertRaises(StudentValidationError):
                validate_student_input(*args)

    def test_non_admin_cannot_open_student_management(self):
        self.as_user(TEACHER)
        with patch("app.services.auth_service.fetch_active_user", return_value=TEACHER):
            response = self.client.get("/admin/students")
        self.assertEqual(response.status_code, 403)

    def test_admin_list_search_and_navigation_render(self):
        self.as_user(ADMIN)
        rows = [{"student_id": 4, "user_id": 44, "nisn": "001234", "full_name": "Siti Aminah",
                 "face_registered": 0, "username": "001234", "is_active": 1, "must_change_password": 1}]
        with patch("app.services.auth_service.fetch_active_user", return_value=ADMIN), \
                patch("app.admin.routes.list_students", return_value=rows) as list_mock:
            response = self.client.get("/admin/students?q=siti")
        self.assertEqual(response.status_code, 200)
        self.assertIn("Siti Aminah", response.get_data(as_text=True))
        self.assertIn("/admin/students/4", response.get_data(as_text=True))
        list_mock.assert_called_once_with("siti")

    def test_admin_can_create_and_receive_one_time_password(self):
        self.as_user(ADMIN)
        created = {"student_id": 5, "user_id": 45, "username": "001234", "nisn": "001234",
                   "full_name": "Siswa Baru", "face_registered": False, "temporary_password": "temporary-only"}
        with patch("app.services.auth_service.fetch_active_user", return_value=ADMIN):
            token = self.token("/admin/students/new")
            with patch("app.admin.routes.create_student", return_value=created) as create_mock:
                response = self.client.post("/admin/students/new", data={
                    "csrf_token": token, "nisn": "001234", "full_name": "Siswa Baru",
                })
        self.assertEqual(response.status_code, 200)
        self.assertIn("temporary-only", response.get_data(as_text=True))
        create_mock.assert_called_once_with(actor_user_id=18, nisn="001234", full_name="Siswa Baru")

    def test_service_errors_are_shown_without_redirecting_to_success(self):
        self.as_user(ADMIN)
        with patch("app.services.auth_service.fetch_active_user", return_value=ADMIN):
            token = self.token("/admin/students/new")
            with patch("app.admin.routes.create_student", side_effect=StudentValidationError("NISN sudah digunakan.")):
                response = self.client.post("/admin/students/new", data={
                    "csrf_token": token, "nisn": "001234", "full_name": "Siswa Baru",
                })
        self.assertEqual(response.status_code, 200)
        self.assertIn("NISN sudah digunakan", response.get_data(as_text=True))


if __name__ == "__main__":
    unittest.main()
