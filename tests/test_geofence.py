"""T13 geofence validation, distance decisions, and Admin smoke coverage."""

from __future__ import annotations

from decimal import Decimal
import unittest
from unittest.mock import patch

from app import create_app
from app.services.auth_service import credential_stamp
from app.services.geofence_service import (
    GeofenceValidationError,
    evaluate_location,
    haversine_meters,
    validate_geofence_config,
)
from werkzeug.security import generate_password_hash


FENCE = {
    "name": "Sekolah sintetis",
    "latitude": Decimal("0.0000000"),
    "longitude": Decimal("0.0000000"),
    "radius_meters": 75,
    "max_accuracy_meters": Decimal("30.00"),
    "is_active": True,
}


class GeofenceTests(unittest.TestCase):
    def test_configuration_requires_both_coordinates_and_policy_before_activation(self):
        with self.assertRaises(GeofenceValidationError):
            validate_geofence_config(name="Sekolah", latitude=0, longitude=None,
                                     radius_meters=75, max_accuracy_meters=30, is_active=False)
        with self.assertRaises(GeofenceValidationError):
            validate_geofence_config(name="Sekolah", latitude=None, longitude=None,
                                     radius_meters=75, max_accuracy_meters=None, is_active=True)

    def test_configuration_rejects_out_of_range_and_non_scalar_values(self):
        for values in (
            {"latitude": 91, "longitude": 0},
            {"latitude": 0, "longitude": -181},
            {"latitude": [0], "longitude": 0},
        ):
            with self.subTest(values=values), self.assertRaises(GeofenceValidationError):
                validate_geofence_config(name="Sekolah", radius_meters=75,
                                         max_accuracy_meters=30, is_active=False, **values)

    def test_haversine_known_equatorial_distance(self):
        distance = haversine_meters(0, 0, 0, 1)
        self.assertAlmostEqual(distance, 111_195.08, delta=0.1)
        self.assertEqual(haversine_meters(0, 0, 0, 0), 0)

    def test_evaluator_handles_center_accuracy_and_radius_boundary(self):
        at_center = evaluate_location(latitude=0, longitude=0, accuracy_meters=30, config=FENCE)
        rough = evaluate_location(latitude=0, longitude=0, accuracy_meters=30.01, config=FENCE)
        invalid = evaluate_location(latitude=[], longitude=0, accuracy_meters=1, config=FENCE)
        self.assertEqual((at_center["allowed"], at_center["reason"]), (True, "inside"))
        self.assertEqual(rough["reason"], "accuracy_unreliable")
        self.assertEqual(invalid["reason"], "invalid_location")
        with patch("app.services.geofence_service.haversine_meters", return_value=75.0):
            boundary = evaluate_location(latitude=0, longitude=0, accuracy_meters=1, config=FENCE)
        with patch("app.services.geofence_service.haversine_meters", return_value=75.01):
            outside = evaluate_location(latitude=0, longitude=0, accuracy_meters=1, config=FENCE)
        self.assertEqual(boundary["reason"], "inside")
        self.assertEqual(outside["reason"], "outside")

    def test_inactive_configuration_never_accepts_location(self):
        inactive = FENCE | {"is_active": False}
        self.assertEqual(evaluate_location(latitude=0, longitude=0, accuracy_meters=1,
                                           config=inactive)["reason"], "not_configured")

    def test_admin_location_check_requires_role_and_valid_json(self):
        app = create_app({"TESTING": True, "SECRET_KEY": "geofence-test"})
        client = app.test_client()
        admin = {"id": 81, "username": "admin.test", "password_hash": generate_password_hash("synthetic-password"),
                 "role": "admin", "is_active": 1, "must_change_password": 0,
                 "face_registered": 0}
        with app.app_context(), client.session_transaction() as session:
            session["user_id"] = admin["id"]
            session["credential_stamp"] = credential_stamp(admin["password_hash"])
        with patch("app.services.auth_service.fetch_active_user", return_value=admin), \
                patch("app.admin.routes.evaluate_location", return_value={"allowed": True, "reason": "inside"}):
            page = client.get("/admin/geofence")
            self.assertEqual(page.status_code, 200)
            token = page.get_data(as_text=True).split('name="csrf_token" value="', 1)[1].split('"', 1)[0]
            bad = client.post("/admin/geofence/check", json=[] , headers={"X-CSRF-Token": token})
            self.assertEqual(bad.status_code, 400)
            good = client.post("/admin/geofence/check", json={"latitude": 0, "longitude": 0,
                                      "accuracy": 3}, headers={"X-CSRF-Token": token})
        self.assertEqual(good.status_code, 200)
        self.assertEqual(good.json["reason"], "inside")


if __name__ == "__main__":
    unittest.main()
