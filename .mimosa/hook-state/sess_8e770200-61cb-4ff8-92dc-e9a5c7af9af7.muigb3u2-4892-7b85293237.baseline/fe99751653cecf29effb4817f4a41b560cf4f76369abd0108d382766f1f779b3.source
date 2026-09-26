"""Regression cases found during the T00-T06 code audit."""

import unittest
from unittest.mock import patch

import numpy as np
from werkzeug.security import generate_password_hash

from app import create_app
from app.services.auth_service import credential_stamp, record_login_failure, is_login_rate_limited
from app.services.face_poc import detect_single_face
from tests.test_profile import ACTIVE_ADMIN


class SecurityRegressionTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app({"TESTING": True, "SECRET_KEY": "regression-test"})
        self.client = self.app.test_client()

    def bind_session(self, account):
        with self.app.app_context(), self.client.session_transaction() as session:
            session["user_id"] = account["id"]
            session["credential_stamp"] = credential_stamp(account["password_hash"])

    def test_old_session_is_revoked_after_password_change(self):
        self.bind_session(ACTIVE_ADMIN)
        replacement = {**ACTIVE_ADMIN, "password_hash": generate_password_hash("new-test-password")}
        with patch("app.services.auth_service.fetch_active_user", return_value=replacement):
            response = self.client.get("/admin/profile")
        self.assertEqual(response.status_code, 302)
        self.assertIn("/login", response.location)
        with self.client.session_transaction() as session:
            self.assertNotIn("user_id", session)

    def test_legacy_session_without_binding_requires_new_login(self):
        with self.client.session_transaction() as session:
            session["user_id"] = ACTIVE_ADMIN["id"]
        with patch("app.services.auth_service.fetch_active_user", return_value=ACTIVE_ADMIN):
            self.assertIn("/login", self.client.get("/admin/dashboard").location)

    def test_non_ascii_csrf_is_400_not_server_error(self):
        self.client.get("/login")
        self.assertEqual(self.client.post("/login", data={"csrf_token": "tidak-sah-💥"}).status_code, 400)

    def test_request_size_is_bounded(self):
        response = self.client.post("/login", data=b"x" * (6 * 1024 * 1024 + 1),
                                    content_type="application/x-www-form-urlencoded")
        self.assertEqual(response.status_code, 413)

    def test_sensitive_responses_are_not_cacheable(self):
        self.bind_session(ACTIVE_ADMIN)
        with patch("app.services.auth_service.fetch_active_user", return_value=ACTIVE_ADMIN):
            response = self.client.get("/admin/profile")
        self.assertEqual(response.headers["Cache-Control"], "no-store")

    def test_production_overrides_cannot_skip_validation(self):
        with self.assertRaises(RuntimeError):
            create_app({"APP_ENV": "production", "SECRET_KEY": "dev-only-change-me"})
        with self.assertRaises(RuntimeError):
            create_app({"APP_ENV": "production", "SECRET_KEY": "synthetic-secret",
                        "DB_PASSWORD": "synthetic", "DEBUG": True})

    def test_login_throttle_has_bounded_memory_and_expiry(self):
        from app.services import auth_service
        with patch.object(auth_service, "_login_failures", auth_service.OrderedDict()), \
                patch.object(auth_service, "MAX_LOGIN_FAILURE_KEYS", 3):
            for i in range(10):
                record_login_failure(str(i), now=0)
            self.assertEqual(len(auth_service._login_failures), 3)
            for _ in range(5):
                record_login_failure("9", now=1)
            self.assertTrue(is_login_rate_limited("9", now=2))
            self.assertFalse(is_login_rate_limited("9", now=61))
            self.assertNotIn("9", auth_service._login_failures)

    def test_face_box_uses_original_frame_coordinates(self):
        class FakeCascade:
            def detectMultiScale(inner, frame, **kwargs):
                self.assertEqual(frame.shape, (480, 640))
                return np.array([[320, 120, 100, 100]])
        with patch("app.services.face_poc._cascade", return_value=FakeCascade()):
            self.assertEqual(detect_single_face(np.zeros((480, 640, 3), dtype=np.uint8)),
                             (320, 120, 100, 100))
