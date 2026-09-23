"""Route/template checks for the T05 role shells and shared styles."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from app import create_app
from app.services.auth_service import credential_stamp


USERS = {
    "admin": {
        "id": 1,
        "username": "admin.test",
        "password_hash": "unused",
        "role": "admin",
        "is_active": 1,
        "must_change_password": 0,
    },
    "teacher": {
        "id": 2,
        "username": "teacher.test",
        "password_hash": "unused",
        "role": "teacher",
        "is_active": 1,
        "must_change_password": 0,
    },
    "student": {
        "id": 3,
        "username": "student.test",
        "password_hash": "unused",
        "role": "student",
        "is_active": 1,
        "must_change_password": 0,
        "face_registered": 1,
    },
}


class RoleShellTests(unittest.TestCase):
    def setUp(self) -> None:
        self.app = create_app({"TESTING": True, "SECRET_KEY": "test-secret"})
        self.client = self.app.test_client()

    def get_as(self, role: str, path: str):
        user = USERS[role]
        with patch("app.services.auth_service.fetch_active_user", return_value=user):
            with self.app.app_context(), self.client.session_transaction() as session:
                session["user_id"] = user["id"]
                session["credential_stamp"] = credential_stamp(user["password_hash"])
            return self.client.get(path)

    def test_home_and_login_use_shared_stylesheet(self) -> None:
        home = self.client.get("/")
        login = self.client.get("/login")
        self.assertEqual(home.status_code, 200)
        self.assertEqual(login.status_code, 200)
        self.assertIn("css/app.css", home.get_data(as_text=True))
        self.assertIn("Masuk ke ruang kerja Anda", login.get_data(as_text=True))

    def test_three_role_shells_render_with_role_navigation(self) -> None:
        cases = (
            ("admin", "/admin/dashboard", "Navigasi Admin", "Monitoring Presensi"),
            ("teacher", "/teacher/dashboard", "Navigasi Guru", "Presensi Kelas"),
            ("student", "/student/dashboard", "Navigasi Siswa", "Riwayat"),
        )
        for role, path, navigation, expected_text in cases:
            with self.subTest(role=role):
                response = self.get_as(role, path)
                body = response.get_data(as_text=True)
                self.assertEqual(response.status_code, 200)
                self.assertIn(navigation, body)
                self.assertIn(expected_text, body)
                self.assertIn("aria-disabled=\"true\"", body)

    def test_compiled_css_is_served_with_prd_tokens(self) -> None:
        response = self.client.get("/static/css/app.css")
        self.assertEqual(response.status_code, 200)
        css = response.get_data(as_text=True)
        response.close()
        self.assertIn("#725cf6", css.lower())
        self.assertIn("#f6f4ee", css.lower())


if __name__ == "__main__":
    unittest.main()
