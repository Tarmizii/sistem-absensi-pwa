"""Attendance state transitions for T17 (T17.4)."""

from __future__ import annotations

from datetime import date, datetime
import secrets
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch

from app import create_app
from app.database import transaction
from app.services.attendance_state_service import determine_action
from app.services.auth_service import credential_stamp
from werkzeug.security import generate_password_hash


def _schedule(**overrides):
    schedule = {
        "for_date": date(2026, 9, 24),
        "checkin_start": "06:30", "late_after": "07:15",
        "checkin_cutoff": "08:00", "checkout_start": "15:00",
        "is_holiday": False, "source": "regular",
        "academic_year_id": 1, "class_id": 1,
        "exception_id": None, "exception_type": None,
    }
    schedule.update(overrides)
    return schedule


def _at(hour: int, minute: int = 0) -> datetime:
    return datetime(2026, 9, 24, hour, minute)


def _record(**overrides):
    record = {"status": None, "status_source": None,
              "checkin_at": None, "checkout_at": None, "class_id": 1}
    record.update(overrides)
    return record


class DetermineActionTests(unittest.TestCase):
    """Pure state machine tests with a controlled clock (no database)."""

    def test_before_start_is_disabled_with_opening_time_reason(self):
        state = determine_action(schedule=_schedule(), record=None, at=_at(6, 0))
        self.assertEqual(state["state"], "before_start")
        self.assertFalse(state["cta_enabled"])
        self.assertEqual(state["cta_label"], "Presensi Masuk")
        self.assertIn("06:30", state["reason"])
        self.assertEqual(state["status_today"], "Belum Absen")

    def test_checkin_window_opens_inclusively_at_start(self):
        state = determine_action(schedule=_schedule(), record=None, at=_at(6, 30))
        self.assertEqual(state["state"], "checkin")
        self.assertTrue(state["cta_enabled"])
        self.assertEqual(state["cta_label"], "Presensi Masuk")
        self.assertEqual(state["predicted_status"], "Hadir")

    def test_checkin_after_late_after_predicts_late(self):
        state = determine_action(schedule=_schedule(), record=None, at=_at(7, 30))
        self.assertEqual(state["state"], "checkin")
        self.assertEqual(state["predicted_status"], "Terlambat")

    def test_checkin_at_exact_cutoff_is_still_allowed(self):
        state = determine_action(schedule=_schedule(), record=None, at=_at(8, 0))
        self.assertEqual(state["state"], "checkin")
        self.assertTrue(state["cta_enabled"])

    def test_after_cutoff_closes_checkin(self):
        state = determine_action(schedule=_schedule(), record=None, at=_at(8, 1))
        self.assertEqual(state["state"], "after_cutoff")
        self.assertFalse(state["cta_enabled"])
        self.assertEqual(state["cta_label"], "Presensi Ditutup")
        self.assertIn("08:00", state["reason"])

    def test_checked_in_waits_until_checkout_start(self):
        state = determine_action(
            schedule=_schedule(), record=_record(checkin_at=_at(7)), at=_at(9))
        self.assertEqual(state["state"], "waiting")
        self.assertFalse(state["cta_enabled"])
        self.assertEqual(state["cta_label"], "Pulang mulai 15:00")
        self.assertIn("15:00", state["reason"])

    def test_checkout_opens_at_checkout_start_inclusively(self):
        state = determine_action(
            schedule=_schedule(), record=_record(checkin_at=_at(7)), at=_at(15))
        self.assertEqual(state["state"], "checkout")
        self.assertTrue(state["cta_enabled"])
        self.assertEqual(state["cta_label"], "Presensi Pulang")

    def test_completed_day_reports_done_and_disables_cta(self):
        state = determine_action(
            schedule=_schedule(),
            record=_record(checkin_at=_at(7), checkout_at=_at(15, 30)),
            at=_at(16))
        self.assertEqual(state["state"], "done")
        self.assertFalse(state["cta_enabled"])
        self.assertEqual(state["cta_label"], "Presensi Selesai")

    def test_holiday_blocks_cta_and_reports_libur(self):
        state = determine_action(
            schedule=_schedule(is_holiday=True), record=None, at=_at(9))
        self.assertEqual(state["state"], "holiday")
        self.assertFalse(state["cta_enabled"])
        self.assertEqual(state["status_today"], "Libur")

    def test_saved_checkin_remains_visible_after_schedule_changes_to_holiday(self):
        state = determine_action(
            schedule=_schedule(is_holiday=True),
            record=_record(status="present", status_source="system", checkin_at=_at(7)),
            at=_at(16))
        self.assertEqual(state["status_today"], "Hadir")
        self.assertEqual(state["state"], "schedule_changed")
        self.assertFalse(state["cta_enabled"])
        self.assertIn("sudah tersimpan", state["reason"])

    def test_saved_checkin_remains_visible_when_schedule_is_removed(self):
        state = determine_action(
            schedule=None,
            record=_record(status="late", status_source="system", checkin_at=_at(7, 30)),
            at=_at(16))
        self.assertEqual(state["status_today"], "Terlambat")
        self.assertEqual(state["state"], "schedule_changed")
        self.assertFalse(state["cta_enabled"])

    def test_manual_status_remains_visible_after_schedule_changes_to_holiday(self):
        state = determine_action(
            schedule=_schedule(is_holiday=True),
            record=_record(status="permit", status_source="teacher"), at=_at(9))
        self.assertEqual(state["state"], "manual_status")
        self.assertEqual(state["status_today"], "Izin")

    def test_manual_status_suppresses_automation_cta(self):
        state = determine_action(
            schedule=_schedule(),
            record=_record(status="permit", status_source="teacher"),
            at=_at(9))
        self.assertEqual(state["state"], "manual_status")
        self.assertFalse(state["cta_enabled"])
        self.assertEqual(state["status_today"], "Izin")
        self.assertEqual(state["status_source"], "teacher")
        self.assertIn("Izin", state["reason"])

    def test_missing_schedule_is_reported_not_crashed(self):
        state = determine_action(schedule=None, record=None, at=_at(9))
        self.assertEqual(state["state"], "no_schedule")
        self.assertFalse(state["cta_enabled"])
        self.assertIsNone(state["schedule"])

    def test_date_rollover_uses_the_new_date_not_the_old_record(self):
        """A finished yesterday must not leak into today (T17.4 pergantian tanggal)."""
        schedule = _schedule(for_date=date(2026, 9, 25),
                             checkin_start="06:30", checkout_start="15:00")
        state = determine_action(schedule=schedule, record=None,
                                 at=datetime(2026, 9, 25, 6, 45))
        self.assertEqual(state["state"], "checkin")
        self.assertTrue(state["cta_enabled"])

    def test_early_dismissal_exception_moves_checkout_earlier(self):
        schedule = _schedule(checkout_start="11:00", source="school",
                             exception_type="early_dismissal")
        state = determine_action(
            schedule=schedule, record=_record(checkin_at=_at(7)), at=_at(11, 30))
        self.assertEqual(state["state"], "checkout")
        self.assertTrue(state["cta_enabled"])


class StudentDashboardRouteTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="t17-")
        self.app = create_app({
            "TESTING": True, "STORAGE_ROOT": str(Path(self.temp.name) / "private"),
        })
        self.client = self.app.test_client()
        self.password_hash = generate_password_hash("TestPassword123!")
        self.csrf = "test-t17-csrf"
        suffix = secrets.token_hex(4)
        with self.app.app_context(), transaction() as (_, cursor):
            cursor.execute(
                "INSERT INTO users (username, password_hash, role, is_active) VALUES (%s, %s, 'student', 1)",
                (f"t17_std_{suffix}", self.password_hash))
            self.user_id = cursor.lastrowid
            cursor.execute(
                "INSERT INTO students (user_id, nisn, full_name, face_registered) VALUES (%s, %s, 'Siswa T17', 1)",
                (self.user_id, f"77{suffix[:8]}"))
            self.student_id = cursor.lastrowid

    def tearDown(self):
        with self.app.app_context():
            try:
                with transaction() as (_, cursor):
                    cursor.execute("DELETE FROM audit_logs WHERE actor_user_id=%s", (self.user_id,))
                    cursor.execute("DELETE FROM attendance_records WHERE student_id=%s", (self.student_id,))
                    cursor.execute("DELETE FROM student_faces WHERE student_id=%s", (self.student_id,))
                    cursor.execute("DELETE FROM students WHERE id=%s", (self.student_id,))
                    cursor.execute("DELETE FROM users WHERE id=%s", (self.user_id,))
            except Exception:
                pass
        self.temp.cleanup()

    def _login(self):
        with self.app.app_context():
            stamp = credential_stamp(self.password_hash)
        with self.client.session_transaction() as session:
            session["user_id"] = self.user_id
            session["role"] = "student"
            session["credential_stamp"] = stamp
            session["_csrf_token"] = self.csrf

    def test_student_dashboard_renders_server_decided_cta(self):
        self._login()
        fake = {
            "student_id": self.student_id, "full_name": "Siswa T17",
            "face_registered": True, "class_name": "X-1",
            "today": "2026-09-24", "server_time": "07:00",
            "state": "checkin", "cta_label": "Presensi Masuk", "cta_enabled": True,
            "reason": None, "status_today": "Belum Absen", "status_source": None,
            "predicted_status": "Hadir",
            "schedule": {"for_date": "2026-09-24", "checkin_start": "06:30",
                         "late_after": "07:15", "checkin_cutoff": "08:00",
                         "checkout_start": "15:00", "is_holiday": False,
                         "source": "regular"},
            "can_checkin": True, "can_checkout_now": False,
        }
        with patch("app.services.attendance_state_service.get_student_day_state", return_value=fake):
            response = self.client.get("/student/dashboard")
        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertIn("Presensi Masuk", html)
        self.assertIn("06:30", html)
        self.assertNotIn("aria-disabled=\"true\"", html.split("Presensi Masuk")[0].split("<article")[-1])

    def test_disabled_cta_shows_reason_and_is_disabled(self):
        self._login()
        fake = {
            "student_id": self.student_id, "full_name": "Siswa T17",
            "face_registered": True, "class_name": None,
            "today": "2026-09-24", "server_time": "05:00",
            "state": "before_start", "cta_label": "Presensi Masuk",
            "cta_enabled": False, "reason": "Presensi dibuka pukul 06:30.",
            "status_today": "Belum Absen", "status_source": None,
            "schedule": {"for_date": "2026-09-24", "checkin_start": "06:30",
                         "late_after": "07:15", "checkin_cutoff": "08:00",
                         "checkout_start": "15:00", "is_holiday": False,
                         "source": "regular"},
            "can_checkin": False, "can_checkout_now": False,
        }
        with patch("app.services.attendance_state_service.get_student_day_state", return_value=fake):
            response = self.client.get("/student/dashboard")
        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertIn("Presensi dibuka pukul 06:30.", html)
        self.assertIn("disabled", html)

    def test_holiday_dashboard_shows_libur_and_no_cta(self):
        self._login()
        fake = {
            "student_id": self.student_id, "full_name": "Siswa T17",
            "face_registered": True, "class_name": None,
            "today": "2026-09-24", "server_time": "09:00",
            "state": "holiday", "cta_label": "Presensi Tidak Tersedia",
            "cta_enabled": False, "reason": "Hari libur; presensi tidak diperlukan.",
            "status_today": "Libur", "status_source": None,
            "schedule": {"for_date": "2026-09-24", "checkin_start": None,
                         "late_after": None, "checkin_cutoff": None,
                         "checkout_start": None, "is_holiday": True,
                         "source": "school"},
            "can_checkin": False, "can_checkout_now": False,
        }
        with patch("app.services.attendance_state_service.get_student_day_state", return_value=fake):
            response = self.client.get("/student/dashboard")
        html = response.get_data(as_text=True)
        self.assertIn("Libur", html)
        self.assertIn("Hari libur", html)

    def test_database_failure_returns_503_with_retry(self):
        self._login()
        from pymysql import MySQLError
        with patch("app.services.attendance_state_service.get_student_day_state",
                   side_effect=MySQLError("db down")):
            response = self.client.get("/student/dashboard")
        self.assertEqual(response.status_code, 503)
        self.assertIn("Coba lagi", response.get_data(as_text=True))

    def test_non_student_cannot_open_dashboard(self):
        teacher_id = None
        with self.app.app_context(), transaction() as (_, cursor):
            cursor.execute(
                "INSERT INTO users (username, password_hash, role, is_active) VALUES (%s, %s, 'teacher', 1)",
                (f"t17_tch_{secrets.token_hex(4)}", self.password_hash))
            teacher_id = cursor.lastrowid
        try:
            with self.app.app_context():
                stamp = credential_stamp(self.password_hash)
            with self.client.session_transaction() as session:
                session["user_id"] = teacher_id
                session["role"] = "teacher"
                session["credential_stamp"] = stamp
                session["_csrf_token"] = self.csrf
            response = self.client.get("/student/dashboard")
            self.assertEqual(response.status_code, 403)
        finally:
            with self.app.app_context():
                with transaction() as (_, cursor):
                    cursor.execute("DELETE FROM users WHERE id=%s", (teacher_id,))


if __name__ == "__main__":
    unittest.main()
