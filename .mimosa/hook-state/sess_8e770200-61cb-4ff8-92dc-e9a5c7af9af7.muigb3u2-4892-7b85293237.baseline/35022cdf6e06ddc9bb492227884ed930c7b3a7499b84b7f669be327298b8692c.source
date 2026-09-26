"""Forced-password and self-profile behavior for T06."""

from __future__ import annotations

import re
import unittest
from unittest.mock import patch

from werkzeug.security import generate_password_hash

from app import create_app
from app.services.auth_service import credential_stamp


CURRENT_PASSWORD = "current-password"


def user(*, user_id: int, username: str, role: str, must_change: int = 0) -> dict:
    return {
        "id": user_id,
        "username": username,
        "password_hash": generate_password_hash(CURRENT_PASSWORD),
        "role": role,
        "is_active": 1,
        "must_change_password": must_change,
    }


FORCED_ADMIN = user(user_id=10, username="temporary.admin", role="admin", must_change=1)
ACTIVE_ADMIN = user(user_id=11, username="admin.profile", role="admin")
ACTIVE_TEACHER = user(user_id=12, username="teacher.profile", role="teacher")


class PasswordAndProfileTests(unittest.TestCase):
    def setUp(self) -> None:
        self.app = create_app({"TESTING": True, "SECRET_KEY": "profile-test-secret"})
        self.client = self.app.test_client()

    def csrf_token(self, path: str = "/change-password") -> str:
        response = self.client.get(path)
        match = re.search(r'name="csrf_token" value="([^"]+)"', response.get_data(as_text=True))
        self.assertIsNotNone(match)
        return match.group(1)

    def set_session(self, user_id: int) -> None:
        users = {u["id"]: u for u in (FORCED_ADMIN, ACTIVE_ADMIN, ACTIVE_TEACHER)}
        with self.app.app_context(), self.client.session_transaction() as session:
            session["user_id"] = user_id
            session["credential_stamp"] = credential_stamp(users[user_id]["password_hash"])

    def test_forced_password_account_cannot_bypass_gate(self) -> None:
        self.set_session(FORCED_ADMIN["id"])
        with patch("app.services.auth_service.fetch_active_user", return_value=FORCED_ADMIN):
            dashboard = self.client.get("/admin/dashboard")
            profile = self.client.get("/admin/profile")
            change = self.client.get("/change-password")

        self.assertEqual(dashboard.status_code, 302)
        self.assertEqual(dashboard.headers["Location"], "/change-password")
        self.assertEqual(profile.status_code, 302)
        self.assertEqual(profile.headers["Location"], "/change-password")
        self.assertEqual(change.status_code, 200)
        self.assertIn("Perbarui password Anda", change.get_data(as_text=True))

    def test_successful_password_change_updates_hash_and_session(self) -> None:
        self.set_session(FORCED_ADMIN["id"])
        with patch("app.services.auth_service.fetch_active_user", return_value=FORCED_ADMIN):
            token = self.csrf_token()
            with patch("app.auth.routes.update_password", return_value="new-stamp") as update_password:
                response = self.client.post(
                    "/change-password",
                    data={
                        "csrf_token": token,
                        "current_password": CURRENT_PASSWORD,
                        "new_password": "new-password-1234",
                        "confirmation": "new-password-1234",
                    },
                )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers["Location"], "/admin/dashboard")
        update_password.assert_called_once_with(FORCED_ADMIN["id"], "new-password-1234", FORCED_ADMIN["password_hash"])
        with self.client.session_transaction() as session:
            self.assertFalse(session["must_change_password"])

    def test_password_change_rejects_wrong_current_short_and_mismatched_passwords(self) -> None:
        self.set_session(ACTIVE_ADMIN["id"])
        cases = [
            (
                "same password",
                {"current_password": CURRENT_PASSWORD, "new_password": CURRENT_PASSWORD, "confirmation": CURRENT_PASSWORD},
                "Password baru harus berbeda",
            ),
            (
                "wrong current",
                {"current_password": "wrong", "new_password": "new-password-1234", "confirmation": "new-password-1234"},
                "Password saat ini salah.",
            ),
            (
                "short new",
                {"current_password": CURRENT_PASSWORD, "new_password": "short", "confirmation": "short"},
                "minimal 12 karakter",
            ),
            (
                "mismatch",
                {"current_password": CURRENT_PASSWORD, "new_password": "new-password-1234", "confirmation": "different-password"},
                "Konfirmasi password tidak sama.",
            ),
        ]
        for name, fields, expected_message in cases:
            with self.subTest(name=name):
                with patch("app.services.auth_service.fetch_active_user", return_value=ACTIVE_ADMIN):
                    token = self.csrf_token()
                    with patch("app.auth.routes.update_password") as update_password:
                        response = self.client.post(
                            "/change-password", data={"csrf_token": token, **fields}
                        )
                self.assertEqual(response.status_code, 200)
                self.assertIn(expected_message, response.get_data(as_text=True))
                update_password.assert_not_called()

    def test_profile_is_scoped_to_current_role_and_shortcut_redirects(self) -> None:
        self.set_session(ACTIVE_TEACHER["id"])
        with patch("app.services.auth_service.fetch_active_user", return_value=ACTIVE_TEACHER):
            own_profile = self.client.get("/teacher/profile")
            shortcut = self.client.get("/profile")
            other_profile = self.client.get("/student/profile")

        self.assertEqual(own_profile.status_code, 200)
        body = own_profile.get_data(as_text=True)
        self.assertIn("teacher.profile", body)
        self.assertIn("Guru/Wali Kelas", body)
        self.assertIn("Belum tersedia", body)
        self.assertEqual(shortcut.status_code, 302)
        self.assertEqual(shortcut.headers["Location"], "/teacher/profile")
        self.assertEqual(other_profile.status_code, 403)


if __name__ == "__main__":
    unittest.main()
