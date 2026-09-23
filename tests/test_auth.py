"""Authentication and role-guard tests using Flask's test client."""

from __future__ import annotations

import re
import unittest
from unittest.mock import patch

from app import create_app
from app.services.auth_service import clear_login_failures, login_attempt_key, credential_stamp


ADMIN = {
    "id": 1,
    "username": "admin.test",
    "password_hash": "unused-in-login-test",
    "role": "admin",
    "is_active": 1,
    "must_change_password": 0,
}
TEACHER = {**ADMIN, "id": 2, "username": "teacher.test", "role": "teacher"}


class AuthTests(unittest.TestCase):
    def setUp(self) -> None:
        self.app = create_app({"TESTING": True, "SECRET_KEY": "test-secret"})
        self.client = self.app.test_client()
        clear_login_failures(login_attempt_key("unknown", "127.0.0.1"))

    def csrf_token(self) -> str:
        response = self.client.get("/login")
        match = re.search(r'name="csrf_token" value="([^"]+)"', response.get_data(as_text=True))
        self.assertIsNotNone(match)
        return match.group(1)

    def test_login_form_has_csrf_and_mutation_without_token_is_rejected(self) -> None:
        token = self.csrf_token()
        self.assertTrue(token)
        response = self.client.post(
            "/login", data={"username": "admin.test", "password": "password"}
        )
        self.assertEqual(response.status_code, 400)

    def test_invalid_login_uses_generic_message(self) -> None:
        token = self.csrf_token()
        with patch("app.auth.routes.authenticate", return_value=None):
            response = self.client.post(
                "/login",
                data={"csrf_token": token, "username": "unknown", "password": "wrong"},
            )
        self.assertEqual(response.status_code, 401)
        self.assertIn("Username atau password salah", response.get_data(as_text=True))

    def test_successful_login_redirects_by_role_and_sets_permanent_session(self) -> None:
        token = self.csrf_token()
        with patch("app.auth.routes.authenticate", return_value=ADMIN):
            response = self.client.post(
                "/login",
                data={"csrf_token": token, "username": "admin.test", "password": "password"},
            )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers["Location"], "/admin/dashboard")
        with self.client.session_transaction() as session:
            self.assertEqual(session["user_id"], 1)
            self.assertTrue(session.permanent)

    def test_logout_uses_regenerated_post_login_csrf_token(self) -> None:
        token = self.csrf_token()
        with patch("app.auth.routes.authenticate", return_value=ADMIN):
            self.client.post(
                "/login",
                data={"csrf_token": token, "username": "admin.test", "password": "password"},
            )
        with patch("app.services.auth_service.fetch_active_user", return_value=ADMIN):
            dashboard = self.client.get("/admin/dashboard")
            match = re.search(r'name="csrf_token" value="([^"]+)"', dashboard.get_data(as_text=True))
            self.assertIsNotNone(match)
            response = self.client.post("/logout", data={"csrf_token": match.group(1)})
            self.assertEqual(response.status_code, 302)
        with self.client.session_transaction() as session:
            self.assertNotIn("user_id", session)

    def test_repeated_failures_are_throttled(self) -> None:
        token = self.csrf_token()
        with patch("app.auth.routes.authenticate", return_value=None):
            for _ in range(5):
                response = self.client.post(
                    "/login",
                    data={"csrf_token": token, "username": "unknown", "password": "wrong"},
                )
                self.assertEqual(response.status_code, 401)
            response = self.client.post(
                "/login",
                data={"csrf_token": token, "username": "unknown", "password": "wrong"},
            )
        self.assertEqual(response.status_code, 429)

    def test_teacher_cannot_open_admin_dashboard(self) -> None:
        with patch("app.services.auth_service.fetch_active_user", return_value=TEACHER):
            with self.app.app_context(), self.client.session_transaction() as session:
                session["user_id"] = 2
                session["credential_stamp"] = credential_stamp(TEACHER["password_hash"])
            response = self.client.get("/admin/dashboard")
        self.assertEqual(response.status_code, 403)

    def test_inactive_or_missing_user_session_is_cleared(self) -> None:
        with patch("app.services.auth_service.fetch_active_user", return_value=None):
            with self.client.session_transaction() as session:
                session["user_id"] = 999
            response = self.client.get("/admin/dashboard")
        self.assertEqual(response.status_code, 302)
        self.assertIn("/login", response.headers["Location"])
        with self.client.session_transaction() as session:
            self.assertNotIn("user_id", session)

    def test_session_cookie_defaults_are_protected(self) -> None:
        self.assertTrue(self.app.config["SESSION_COOKIE_HTTPONLY"])
        self.assertEqual(self.app.config["SESSION_COOKIE_SAMESITE"], "Lax")
        self.assertFalse(self.app.config["SESSION_COOKIE_SECURE"])


if __name__ == "__main__":
    unittest.main()
