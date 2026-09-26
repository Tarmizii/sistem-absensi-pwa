"""T10 master academic year, class, and placement route tests."""

from __future__ import annotations

import re
import unittest
from datetime import date
from unittest.mock import patch

from werkzeug.security import generate_password_hash

from app import create_app
from app.services.auth_service import credential_stamp
from app.services.class_service import (
    MasterDataValidationError,
    validate_academic_year_input,
    validate_class_input,
)


ADMIN = {"id": 18, "username": "admin", "password_hash": generate_password_hash("synthetic-admin"),
         "role": "admin", "is_active": 1, "must_change_password": 0}
TEACHER = {"id": 19, "username": "teacher.test", "password_hash": generate_password_hash("synthetic-teacher"),
           "role": "teacher", "is_active": 1, "must_change_password": 0}


class ClassMasterTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app({"TESTING": True, "SECRET_KEY": "class-test"})
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

    def test_academic_year_and_class_validation(self):
        self.assertEqual(validate_academic_year_input(" 2026/2027 ", "2026-07-01", "2027-06-30"),
                         ("2026/2027", date(2026, 7, 1), date(2027, 6, 30)))
        with self.assertRaises(MasterDataValidationError):
            validate_academic_year_input("2026-2027", "2026-07-01", "2027-06-30")
        with self.assertRaises(MasterDataValidationError):
            validate_academic_year_input("2026/2027", "2027-07-01", "2026-06-30")
        self.assertEqual(validate_class_input("  X   IPA 1 ", 4, None), ("X IPA 1", 4, None))
        with self.assertRaises(MasterDataValidationError):
            validate_class_input("X\nIPA", 4)

    def test_non_admin_cannot_open_class_management(self):
        self.as_user(TEACHER)
        with patch("app.services.auth_service.fetch_active_user", return_value=TEACHER):
            response = self.client.get("/admin/classes")
        self.assertEqual(response.status_code, 403)

    def test_admin_class_list_renders_active_master_data(self):
        self.as_user(ADMIN)
        years = [{"id": 4, "name": "2026/2027", "start_date": "2026-07-01", "end_date": "2027-06-30", "is_active": 1}]
        classes = [{"class_id": 8, "academic_year_id": 4, "name": "X IPA 1", "academic_year_name": "2026/2027",
                    "teacher_id": 3, "teacher_name": "Siti Aminah", "student_count": 12, "is_active": 1}]
        with patch("app.services.auth_service.fetch_active_user", return_value=ADMIN), \
                patch("app.admin.routes.list_academic_years", return_value=years), \
                patch("app.admin.routes.list_teacher_options", return_value=[]), \
                patch("app.admin.routes.list_classes", return_value=classes):
            response = self.client.get("/admin/classes")
        self.assertEqual(response.status_code, 200)
        body = response.get_data(as_text=True)
        self.assertIn("X IPA 1", body)
        self.assertIn("2026/2027", body)
        self.assertIn("/admin/classes/8", body)

    def test_admin_can_create_academic_year(self):
        self.as_user(ADMIN)
        with patch("app.services.auth_service.fetch_active_user", return_value=ADMIN):
            token = self.token("/admin/academic-years")
            with patch("app.admin.routes.create_academic_year", return_value={"id": 4}) as create_mock, \
                    patch("app.admin.routes.list_academic_years", return_value=[]):
                response = self.client.post("/admin/academic-years", data={
                    "csrf_token": token, "name": "2026/2027", "start_date": "2026-07-01",
                    "end_date": "2027-06-30", "is_active": "on",
                })
        self.assertEqual(response.status_code, 302)
        create_mock.assert_called_once_with(actor_user_id=18, name="2026/2027",
                                             start_date="2026-07-01", end_date="2027-06-30", is_active=True)

    def test_admin_can_assign_student_to_class(self):
        self.as_user(ADMIN)
        with patch("app.services.auth_service.fetch_active_user", return_value=ADMIN):
            token = self.token("/admin/classes")
            with patch("app.admin.routes.assign_student", return_value={"enrollment_id": 10}) as assign_mock:
                response = self.client.post("/admin/classes/8/students/add", data={
                    "csrf_token": token, "student_id": "12",
                })
        self.assertEqual(response.status_code, 302)
        assign_mock.assert_called_once_with(actor_user_id=18, class_id=8, student_id=12)

    def test_master_service_error_is_shown(self):
        self.as_user(ADMIN)
        with patch("app.services.auth_service.fetch_active_user", return_value=ADMIN):
            token = self.token("/admin/classes")
            with patch("app.admin.routes.create_class", side_effect=MasterDataValidationError("Nama kelas sudah digunakan.")), \
                    patch("app.admin.routes.list_academic_years", return_value=[]), \
                    patch("app.admin.routes.list_teacher_options", return_value=[]), \
                    patch("app.admin.routes.list_classes", return_value=[]):
                response = self.client.post("/admin/classes", data={
                    "csrf_token": token, "name": "X IPA 1", "academic_year_id": "4",
                })
        self.assertEqual(response.status_code, 200)
        self.assertIn("Nama kelas sudah digunakan", response.get_data(as_text=True))


if __name__ == "__main__":
    unittest.main()
