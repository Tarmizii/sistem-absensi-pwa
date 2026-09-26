"""T21 student read models, privacy boundaries, and date validation."""

from __future__ import annotations

from datetime import datetime, timezone
import unittest
from unittest.mock import patch

from app import create_app
from app.services.attendance_read_service import (
    AttendanceReadError,
    escape_like_pattern,
    parse_month,
    parse_page,
)
from app.services.auth_service import credential_stamp
from app.services.schedule_service import database_datetime_to_local_time
from werkzeug.security import generate_password_hash


class AttendanceReadParameterTests(unittest.TestCase):
    def test_parse_month_handles_december_and_leap_february(self):
        self.assertEqual(parse_month("2026-12")[:2],
                         (datetime(2026, 12, 1).date(), datetime(2027, 1, 1).date()))
        self.assertEqual(parse_month("2024-02")[:2],
                         (datetime(2024, 2, 1).date(), datetime(2024, 3, 1).date()))

    def test_month_and_page_inputs_are_strict(self):
        for value in (None, "2026-00", "2026-13", "2026-2", "2026-02x", "２０２６-０２"):
            with self.subTest(value=value), self.assertRaises(AttendanceReadError):
                parse_month(value)
        for value in ("0", "-1", "+1", "1.0", "１２"):
            with self.subTest(value=value), self.assertRaises(AttendanceReadError):
                parse_page(value)
        self.assertEqual(parse_page("25"), 25)

    def test_naive_mysql_utc_time_is_formatted_in_jakarta(self):
        app = create_app({"TESTING": True, "APP_TIMEZONE": "Asia/Jakarta"})
        with app.app_context():
            self.assertEqual(database_datetime_to_local_time(datetime(2026, 9, 23, 23, 45)), "06:45")
            self.assertEqual(database_datetime_to_local_time(
                datetime(2026, 9, 24, 0, 5, tzinfo=timezone.utc)), "07:05")
            self.assertIsNone(database_datetime_to_local_time(None))


class StudentAttendanceReadRouteTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app({"TESTING": True, "SECRET_KEY": "attendance-read-test"})
        self.client = self.app.test_client()
        self.password_hash = generate_password_hash("SyntheticPass12345")
        self.user = {"id": 841, "username": "student-read", "password_hash": self.password_hash,
                     "role": "student", "is_active": 1, "must_change_password": 0,
                     "face_registered": 1}
        with self.app.app_context(), self.client.session_transaction() as session:
            session["user_id"] = self.user["id"]
            session["credential_stamp"] = credential_stamp(self.password_hash)
            session["_csrf_token"] = "test-csrf"

    def _active_user(self):
        return patch("app.services.auth_service.fetch_active_user", return_value=self.user)

    def test_status_endpoint_uses_server_state_and_omits_internal_fields(self):
        fake = {
            "student_id": 101, "face_registered": True, "model_path": "private/model.yml",
            "full_name": "Siswa Uji", "class_name": "X-1", "today": "2026-09-24",
            "server_time": "08:00", "status_today": "Hadir", "status_source": "finalization_job",
            "status_source_label": "Sistem", "checkin_time": "07:00", "checkout_time": None,
            "state": "waiting", "cta_label": "Pulang mulai 15:00", "cta_enabled": False,
            "reason": "Menunggu jadwal.", "schedule": {"checkin_start": "06:30",
                "late_after": "07:15", "checkin_cutoff": "08:00", "checkout_start": "15:00",
                "is_holiday": False, "class_id": 9, "exception_id": 8,
                "source": "regular", "checkin_photo": "private.jpg"},
        }
        with self._active_user(), patch("app.student.routes.get_student_day_state", return_value=fake):
            response = self.client.get("/student/attendance-state")
        self.assertEqual(response.status_code, 200)
        body = response.get_json()
        self.assertEqual(body["status_source_label"], "Sistem")
        self.assertEqual(body["schedule"], {
            "checkin_start": "06:30", "late_after": "07:15", "checkin_cutoff": "08:00",
            "checkout_start": "15:00", "is_holiday": False,
        })
        serialized = response.get_data(as_text=True)
        for forbidden in ("student_id", "model_path", "finalization_job", "checkin_photo", "exception_id"):
            self.assertNotIn(forbidden, serialized)
        self.assertEqual(response.headers["Cache-Control"], "no-store")

    def test_identity_parameters_are_rejected_without_reading_data(self):
        with self._active_user(), patch("app.student.routes.get_student_day_state") as read_state:
            response = self.client.get("/student/attendance-state?student_id=9")
        self.assertEqual(response.status_code, 400)
        read_state.assert_not_called()

    def test_old_month_and_invalid_month_are_rejected_before_database_access(self):
        with self._active_user():
            old = self.client.get("/student/history?month=2020-01")
            invalid = self.client.get("/student/history?month=2026-13")
        self.assertEqual(old.status_code, 403)
        self.assertEqual(invalid.status_code, 400)

    def test_calendar_route_renders_only_owned_read_model(self):
        month = "2026-09"
        sample = {
            "full_name": "Siswa Uji", "month": month, "month_label": "September 2026",
            "weeks": [[None, {"date": "2026-09-24", "day": 24, "status": "Hadir",
                               "status_key": "present", "is_future": False}]],
            "detail": {"date": "2026-09-24", "status": "Hadir", "status_key": "present",
                       "is_future": False, "checkin_time": "07:00", "checkout_time": None,
                       "notes": None, "source": "Sistem"},
            "selected_date": "2026-09-24", "today": "2026-09-24",
        }
        with self._active_user(), patch("app.student.routes.get_student_month_history", return_value=sample) as read:
            response = self.client.get(f"/student/history?month={month}&date=2026-09-24")
        self.assertEqual(response.status_code, 200)
        read.assert_called_once_with(self.user["id"], month, "2026-09-24")
        body = response.get_data(as_text=True)
        self.assertIn("Kalender presensi bulan berjalan", body)
        self.assertIn("Hadir", body)
        self.assertNotIn("checkin_photo", body)


class EscapeLikePatternTests(unittest.TestCase):
    def test_wildcards_and_backslash_become_literal(self):
        self.assertEqual(escape_like_pattern("Rani"), "Rani")
        self.assertEqual(escape_like_pattern("100%"), "100\\%")
        self.assertEqual(escape_like_pattern("a_b"), "a\\_b")
        self.assertEqual(escape_like_pattern("a\\b"), "a\\\\b")
        self.assertEqual(escape_like_pattern("%_%\\"), "\\%\\_\\%\\\\")
        self.assertEqual(escape_like_pattern(""), "")


if __name__ == "__main__":
    unittest.main()
