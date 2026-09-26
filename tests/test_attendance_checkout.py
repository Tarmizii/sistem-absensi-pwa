"""Check-out validation contract for T19: preflight, same-record update, idempotency."""

from __future__ import annotations

from datetime import datetime
from io import BytesIO
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch

import numpy as np
from PIL import Image
from werkzeug.security import generate_password_hash

from app import create_app
from app.services.attendance_service import (
    AttendanceError,
    _DuplicateCheckout,
    process_checkout_frame,
    start_checkout,
)
from app.services.auth_service import credential_stamp
from app.services.face_enrollment_service import FrameAssessment


def jpeg_frame() -> bytes:
    output = BytesIO()
    Image.new("RGB", (200, 200), (110, 110, 110)).save(output, format="JPEG")
    return output.getvalue()


def _context(*, state=None, face_registered=True, model_path="models/abc123.yml"):
    base_state = {
        "state": "checkout", "cta_label": "Presensi Pulang", "cta_enabled": True,
        "reason": None, "status_today": "Hadir", "status_source": "system",
        "can_checkin": False, "can_checkout_now": True,
    }
    return {
        "student": {"student_id": 44, "full_name": "Siswa Uji",
                    "face_registered": face_registered, "model_path": model_path},
        "placement": {"class_id": 7, "class_name": "X-1", "academic_year_id": 1},
        "record": None,
        "schedule": {"checkin_start": "06:30", "late_after": "07:15",
                     "checkin_cutoff": "08:00", "checkout_start": "15:00",
                     "is_holiday": False, "source": "regular"},
        "state": {**base_state, **(state or {})},
        "class_id": 7, "for_date": None,
        "moment": datetime(2026, 9, 24, 16, 0),
    }


def _session_with_checkout_challenge(app, token="t" * 43, stage="await_open"):
    with app.test_request_context("/"):
        from flask import session
        session["_attendance_checkout"] = {
            "token": token, "stage": stage, "expires": 9999999999.0,
            "latitude": "-6.2", "longitude": "106.8", "accuracy": "5",
        }
        yield session


class StartCheckoutTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app({"TESTING": True, "SECRET_KEY": "checkout-test"})

    def test_requires_registered_face_with_model(self):
        with self.app.test_request_context("/"):
            with patch("app.services.attendance_service.load_day_context",
                       return_value=_context(face_registered=False)):
                with self.assertRaises(AttendanceError) as caught:
                    start_checkout(201, latitude="-6.2", longitude="106.8", accuracy_meters="5")
        self.assertEqual(caught.exception.status_code, 409)

    def test_refuses_before_checkout_start(self):
        state = {"state": "waiting", "cta_label": "Pulang mulai 15:00",
                 "cta_enabled": False, "can_checkout_now": False,
                 "reason": "Presensi pulang dapat dilakukan mulai 15:00."}
        with self.app.test_request_context("/"):
            with patch("app.services.attendance_service.load_day_context",
                       return_value=_context(state=state)):
                with self.assertRaises(AttendanceError) as caught:
                    start_checkout(201, latitude="-6.2", longitude="106.8", accuracy_meters="5")
        self.assertEqual(caught.exception.status_code, 409)

    def test_refuses_without_checkin(self):
        state = {"state": "checkin", "cta_label": "Presensi Masuk",
                 "cta_enabled": True, "can_checkin": True, "can_checkout_now": False,
                 "reason": None}
        with self.app.test_request_context("/"):
            with patch("app.services.attendance_service.load_day_context",
                       return_value=_context(state=state)):
                with self.assertRaises(AttendanceError) as caught:
                    start_checkout(201, latitude="-6.2", longitude="106.8", accuracy_meters="5")
        self.assertEqual(caught.exception.status_code, 409)

    def test_rejects_outside_geofence_without_opening_camera(self):
        with self.app.test_request_context("/"):
            with patch("app.services.attendance_service.load_day_context",
                       return_value=_context()), \
                    patch("app.services.attendance_service.evaluate_location",
                          return_value={"allowed": False, "reason": "outside",
                                        "distance_meters": 5000.0}):
                with self.assertRaises(AttendanceError) as caught:
                    start_checkout(201, latitude="0", longitude="0", accuracy_meters="5")
        self.assertEqual(caught.exception.status_code, 422)
        self.assertIn("luar area sekolah", str(caught.exception))

    def test_rejects_unreliable_accuracy(self):
        with self.app.test_request_context("/"):
            with patch("app.services.attendance_service.load_day_context",
                       return_value=_context()), \
                    patch("app.services.attendance_service.evaluate_location",
                          return_value={"allowed": False, "reason": "accuracy_unreliable",
                                        "distance_meters": None}):
                with self.assertRaises(AttendanceError) as caught:
                    start_checkout(201, latitude="-6.2", longitude="106.8", accuracy_meters="500")
        self.assertEqual(caught.exception.status_code, 422)

    def test_accepts_inside_location_and_binds_challenge(self):
        with self.app.test_request_context("/"):
            with patch("app.services.attendance_service.load_day_context",
                       return_value=_context()), \
                    patch("app.services.attendance_service.evaluate_location",
                          return_value={"allowed": True, "reason": "inside",
                                        "distance_meters": 10.0}):
                result = start_checkout(201, latitude="-6.2", longitude="106.8",
                                        accuracy_meters="5")
        self.assertIn("challenge_id", result)
        self.assertEqual(result["expires_in"], 45)


class ProcessCheckoutFrameTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app({"TESTING": True, "SECRET_KEY": "checkout-frame-test"})
        self.crop = np.full((80, 90, 3), 120, dtype=np.uint8)

    def _assessment(self, valid=True, eyes=2):
        return FrameAssessment(valid, "ok", eyes, self.crop.copy() if valid else None)

    def test_unknown_token_is_rejected(self):
        with self.app.test_request_context("/"):
            from flask import session
            session["_attendance_checkout"] = {
                "token": "a" * 43, "stage": "await_open", "expires": 9999999999.0,
                "latitude": "-6.2", "longitude": "106.8", "accuracy": "5",
            }
            with self.assertRaises(AttendanceError) as caught:
                process_checkout_frame(201, "b" * 43, jpeg_frame(), "image/jpeg")
        self.assertEqual(caught.exception.status_code, 400)

    def test_missing_challenge_requires_a_fresh_start(self):
        with self.app.test_request_context("/"):
            with self.assertRaises(AttendanceError) as caught:
                process_checkout_frame(201, "c" * 43, jpeg_frame(), "image/jpeg")
        self.assertEqual(caught.exception.status_code, 410)

    def test_expired_challenge_is_rejected(self):
        with self.app.test_request_context("/"):
            from flask import session
            session["_attendance_checkout"] = {
                "token": "t" * 43, "stage": "await_open", "expires": 1.0,
                "latitude": "-6.2", "longitude": "106.8", "accuracy": "5",
            }
            with self.assertRaises(AttendanceError) as caught:
                process_checkout_frame(201, "t" * 43, jpeg_frame(), "image/jpeg")
        self.assertEqual(caught.exception.status_code, 410)

    def test_liveness_progresses_without_any_write(self):
        with self.app.test_request_context("/"):
            from flask import session
            session["_attendance_checkout"] = {
                "token": "t" * 43, "stage": "await_open", "expires": 9999999999.0,
                "latitude": "-6.2", "longitude": "106.8", "accuracy": "5",
            }
            with patch("app.services.attendance_service._inspect_frame",
                       return_value=self._assessment(True, eyes=2)):
                outcome = process_checkout_frame(201, "t" * 43, jpeg_frame(), "image/jpeg")
        self.assertFalse(outcome.captured)
        self.assertEqual(outcome.stage, "await_closed")

    def test_identity_mismatch_rejects_without_persisting(self):
        with self.app.test_request_context("/"):
            from flask import session
            session["_attendance_checkout"] = {
                "token": "t" * 43, "stage": "await_reopen", "expires": 9999999999.0,
                "latitude": "-6.2", "longitude": "106.8", "accuracy": "5",
            }
            with patch("app.services.attendance_service._inspect_frame",
                       return_value=self._assessment(True, eyes=2)), \
                    patch("app.services.attendance_service.load_day_context",
                          return_value=_context()), \
                    patch("app.services.attendance_service._identity_match",
                          return_value=(False, 120.0)):
                with self.assertRaises(AttendanceError) as caught:
                    process_checkout_frame(201, "t" * 43, jpeg_frame(), "image/jpeg")
        self.assertEqual(caught.exception.status_code, 403)

    def test_capture_persists_through_store_checkout_record(self):
        stored = {"captured": True, "checkout": True,
                  "message": "Presensi pulang berhasil dicatat."}
        with self.app.test_request_context("/"):
            from flask import session
            session["_attendance_checkout"] = {
                "token": "t" * 43, "stage": "await_reopen", "expires": 9999999999.0,
                "latitude": "-6.2", "longitude": "106.8", "accuracy": "5",
            }
            with patch("app.services.attendance_service._inspect_frame",
                       return_value=self._assessment(True, eyes=2)), \
                    patch("app.services.attendance_service.load_day_context",
                          return_value=_context()), \
                    patch("app.services.attendance_service._identity_match",
                          return_value=(True, 40.0)), \
                    patch("app.services.attendance_service._store_checkout_record",
                          return_value=stored) as store:
                outcome = process_checkout_frame(201, "t" * 43, jpeg_frame(), "image/jpeg")
        self.assertTrue(outcome.captured)
        self.assertEqual(outcome.result, stored)
        store.assert_called_once()

    def test_duplicate_checkout_returns_existing_without_insert(self):
        from app.services.attendance_service import _DuplicateCheckout
        with self.app.test_request_context("/"):
            from flask import session
            session["_attendance_checkout"] = {
                "token": "t" * 43, "stage": "await_reopen", "expires": 9999999999.0,
                "latitude": "-6.2", "longitude": "106.8", "accuracy": "5",
            }
            with patch("app.services.attendance_service._inspect_frame",
                       return_value=self._assessment(True, eyes=2)), \
                    patch("app.services.attendance_service.load_day_context",
                          return_value=_context()), \
                    patch("app.services.attendance_service._identity_match",
                          return_value=(True, 40.0)), \
                    patch("app.services.attendance_service._store_checkout_record",
                          side_effect=_DuplicateCheckout({"status": "present"})):
                outcome = process_checkout_frame(201, "t" * 43, jpeg_frame(), "image/jpeg")
        self.assertTrue(outcome.captured)
        self.assertTrue(outcome.result["duplicate"])
        self.assertTrue(outcome.result["checkout"])

    def test_checkin_challenge_cannot_be_used_for_checkout(self):
        with self.app.test_request_context("/"):
            from flask import session
            # Only a check-in challenge exists; checkout must require its own.
            session["_attendance_checkin"] = {
                "token": "t" * 43, "stage": "await_reopen", "expires": 9999999999.0,
                "latitude": "-6.2", "longitude": "106.8", "accuracy": "5",
            }
            with self.assertRaises(AttendanceError) as caught:
                process_checkout_frame(201, "t" * 43, jpeg_frame(), "image/jpeg")
        self.assertEqual(caught.exception.status_code, 410)


class CheckoutRouteTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.app = create_app({
            "TESTING": True, "SECRET_KEY": "checkout-route-test",
            "STORAGE_ROOT": str(Path(self.temp.name) / "private"),
        })
        self.client = self.app.test_client()
        self.user = {
            "id": 201, "username": "student-201",
            "password_hash": generate_password_hash("synthetic-password"),
            "role": "student", "is_active": 1, "must_change_password": 0,
            "face_registered": 1,
        }
        with self.app.app_context(), self.client.session_transaction() as session:
            session["user_id"] = self.user["id"]
            session["credential_stamp"] = credential_stamp(self.user["password_hash"])
            session["_csrf_token"] = "test-csrf-token"

    def _active_user(self, user=None):
        return patch("app.services.auth_service.fetch_active_user", return_value=user or self.user)

    def test_start_requires_a_location_object(self):
        with self._active_user():
            response = self.client.post(
                "/attendance/checkout/start", json=["bad"],
                headers={"X-CSRF-Token": "test-csrf-token"},
            )
        self.assertEqual(response.status_code, 400)

    def test_start_maps_service_status_codes(self):
        with self._active_user():
            with patch("app.attendance.routes.start_checkout",
                       side_effect=AttendanceError("belum dibuka", 409)):
                denied = self.client.post(
                    "/attendance/checkout/start",
                    json={"latitude": "0", "longitude": "0", "accuracy": "5"},
                    headers={"X-CSRF-Token": "test-csrf-token"},
                )
        self.assertEqual(denied.status_code, 409)
        self.assertIn("belum dibuka", denied.json["error"])
        self.assertFalse(denied.json["retry"])

        with self._active_user():
            with patch("app.attendance.routes.start_checkout",
                       side_effect=AttendanceError("boom", 503)):
                failed = self.client.post(
                    "/attendance/checkout/start",
                    json={"latitude": "0", "longitude": "0", "accuracy": "5"},
                    headers={"X-CSRF-Token": "test-csrf-token"},
                )
        self.assertEqual(failed.status_code, 503)
        self.assertTrue(failed.json["retry"])

    def test_frame_requires_a_camera_file(self):
        with self._active_user():
            response = self.client.post(
                "/attendance/checkout/frame", data={"challenge_id": "t" * 43},
                headers={"X-CSRF-Token": "test-csrf-token"},
            )
        self.assertEqual(response.status_code, 400)

    def test_frame_maps_identity_rejection(self):
        with self._active_user():
            with patch("app.attendance.routes.process_checkout_frame",
                       side_effect=AttendanceError("Wajah tidak cocok", 403)):
                response = self.client.post(
                    "/attendance/checkout/frame",
                    data={"challenge_id": "t" * 43,
                          "frame": (BytesIO(jpeg_frame()), "cam.jpg", "image/jpeg")},
                    headers={"X-CSRF-Token": "test-csrf-token"},
                )
        self.assertEqual(response.status_code, 403)

    def test_teacher_cannot_start_checkout(self):
        teacher = self.user | {"role": "teacher"}
        with self._active_user(teacher):
            response = self.client.post(
                "/attendance/checkout/start",
                json={"latitude": "0", "longitude": "0", "accuracy": "5"},
                headers={"X-CSRF-Token": "test-csrf-token"},
            )
        self.assertEqual(response.status_code, 403)


if __name__ == "__main__":
    unittest.main()
