"""T11 regular schedule validation, boundaries, and Admin routes."""

from __future__ import annotations

import re
import unittest
from datetime import datetime, time
from unittest.mock import patch

from werkzeug.security import generate_password_hash

from app import create_app
from app.services.auth_service import credential_stamp
from app.services.schedule_service import (
    ScheduleValidationError,
    can_checkout,
    evaluate_checkin,
    validate_schedule_input,
)


ADMIN = {"id": 18, "username": "admin", "password_hash": generate_password_hash("synthetic-admin"),
         "role": "admin", "is_active": 1, "must_change_password": 0}
TEACHER = {"id": 19, "username": "teacher.test", "password_hash": generate_password_hash("synthetic-teacher"),
           "role": "teacher", "is_active": 1, "must_change_password": 0}


class ScheduleTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app({"TESTING": True, "SECRET_KEY": "schedule-test"})
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

    def test_schedule_validation_and_order(self):
        values = validate_schedule_input(academic_year_id=4, day_of_week=5,
                                         checkin_start="07:00", late_after="07:15",
                                         checkin_cutoff="08:00", checkout_start="15:00")
        self.assertEqual(values[0:2], (4, 5))
        self.assertEqual(values[2:], (time(7), time(7, 15), time(8), time(15), True))
        with self.assertRaises(ScheduleValidationError):
            validate_schedule_input(academic_year_id=4, day_of_week=5,
                                    checkin_start="08:00", late_after="07:15",
                                    checkin_cutoff="08:00", checkout_start="15:00")
        with self.assertRaises(ScheduleValidationError):
            validate_schedule_input(academic_year_id=4, day_of_week=8,
                                    checkin_start="07:00", late_after="07:15",
                                    checkin_cutoff="08:00", checkout_start="15:00")

    def test_checkin_boundaries_are_server_rule_boundaries(self):
        schedule = {"checkin_start": time(7), "late_after": time(7, 15),
                    "checkin_cutoff": time(8), "checkout_start": time(15)}
        self.assertEqual(evaluate_checkin(schedule, datetime(2026, 9, 22, 6, 59))["state"], "before_start")
        self.assertEqual(evaluate_checkin(schedule, datetime(2026, 9, 22, 7, 0))["status"], "present")
        self.assertEqual(evaluate_checkin(schedule, datetime(2026, 9, 22, 7, 15))["status"], "late")
        self.assertTrue(evaluate_checkin(schedule, datetime(2026, 9, 22, 8, 0))["allowed"])
        self.assertFalse(evaluate_checkin(schedule, datetime(2026, 9, 22, 8, 1))["allowed"])
        self.assertFalse(can_checkout(schedule, datetime(2026, 9, 22, 14, 59)))
        self.assertTrue(can_checkout(schedule, datetime(2026, 9, 22, 15, 0)))

    def test_non_admin_cannot_open_schedule_management(self):
        self.as_user(TEACHER)
        with patch("app.services.auth_service.fetch_active_user", return_value=TEACHER):
            response = self.client.get("/admin/schedules")
        self.assertEqual(response.status_code, 403)

    def test_admin_schedule_list_renders(self):
        self.as_user(ADMIN)
        years = [{"id": 4, "name": "2026/2027", "start_date": "2026-07-01", "end_date": "2027-06-30", "is_active": 1}]
        schedules = [{"schedule_id": 9, "academic_year_id": 4, "academic_year_name": "2026/2027",
                      "day_of_week": 5, "checkin_start": "07:00", "late_after": "07:15",
                      "checkin_cutoff": "08:00", "checkout_start": "15:00", "is_active": 1}]
        with patch("app.services.auth_service.fetch_active_user", return_value=ADMIN), \
                patch("app.services.class_service.list_academic_years", return_value=years), \
                patch("app.admin.routes.list_schedules", return_value=schedules):
            response = self.client.get("/admin/schedules")
        self.assertEqual(response.status_code, 200)
        self.assertIn("Jumat", response.get_data(as_text=True))
        self.assertIn("07:15", response.get_data(as_text=True))
        self.assertIn("/admin/schedules/9/edit", response.get_data(as_text=True))

    def test_admin_can_create_schedule(self):
        self.as_user(ADMIN)
        with patch("app.services.auth_service.fetch_active_user", return_value=ADMIN):
            token = self.token("/admin/schedules")
            with patch("app.admin.routes.create_schedule", return_value={"schedule_id": 9}) as create_mock, \
                    patch("app.services.class_service.list_academic_years", return_value=[]), \
                    patch("app.admin.routes.list_schedules", return_value=[]):
                response = self.client.post("/admin/schedules", data={
                    "csrf_token": token, "academic_year_id": "4", "day_of_week": "5",
                    "checkin_start": "07:00", "late_after": "07:15", "checkin_cutoff": "08:00",
                    "checkout_start": "15:00", "is_active": "on",
                })
        self.assertEqual(response.status_code, 302)
        create_mock.assert_called_once_with(actor_user_id=18, academic_year_id=4, day_of_week=5,
                                             checkin_start="07:00", late_after="07:15",
                                             checkin_cutoff="08:00", checkout_start="15:00", is_active=True)

    def test_schedule_validation_error_is_shown(self):
        self.as_user(ADMIN)
        with patch("app.services.auth_service.fetch_active_user", return_value=ADMIN):
            token = self.token("/admin/schedules")
            with patch("app.admin.routes.create_schedule", side_effect=ScheduleValidationError("Urutan waktu tidak valid.")), \
                    patch("app.services.class_service.list_academic_years", return_value=[]), \
                    patch("app.admin.routes.list_schedules", return_value=[]):
                response = self.client.post("/admin/schedules", data={
                    "csrf_token": token, "academic_year_id": "4", "day_of_week": "5",
                    "checkin_start": "08:00", "late_after": "07:15", "checkin_cutoff": "08:00",
                    "checkout_start": "15:00", "is_active": "on",
                })
        self.assertEqual(response.status_code, 200)
        self.assertIn("Urutan waktu tidak valid", response.get_data(as_text=True))


if __name__ == "__main__":
    unittest.main()
