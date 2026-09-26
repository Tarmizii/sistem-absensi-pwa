"""T24 manual-status validation and route boundaries."""

from __future__ import annotations

import unittest
from datetime import datetime
from zoneinfo import ZoneInfo
from unittest.mock import MagicMock, patch

from app import create_app
from app.services.auth_service import credential_stamp
from app.services.manual_attendance_service import (
    ManualAttendanceError,
    set_manual_attendance_status,
    validate_manual_status_input,
)
from werkzeug.security import generate_password_hash


class ManualAttendanceInputTests(unittest.TestCase):
    def test_existing_record_requires_matching_class_snapshot_before_any_write(self):
        for snapshot in (13, None):
            for action in ("permit", "clear"):
                with self.subTest(snapshot=snapshot, action=action):
                    cursor = MagicMock()
                    cursor.fetchone.side_effect = [
                        {"academic_year_id": 1, "class_id": 12},
                        {"id": 88, "class_id": snapshot, "status": "permit",
                         "status_source": "teacher", "checkin_at": None, "checkout_at": None},
                    ]
                    cursor.rowcount = 1
                    tx = MagicMock()
                    tx.__enter__.return_value = (None, cursor)
                    with patch("app.services.manual_attendance_service.transaction", return_value=tx), \
                            patch("app.services.manual_attendance_service.resolve_schedule",
                                  return_value={"is_holiday": False, "checkin_cutoff": "08:00"}), \
                            patch("app.services.manual_attendance_service.record_audit"), \
                            self.assertRaises(ManualAttendanceError) as rejected:
                        set_manual_attendance_status(
                            teacher_user_id=940, student_id=841, class_value="12",
                            status_value=action, notes_value="Alasan" if action == "permit" else "",
                            at=datetime(2026, 9, 24, 7, tzinfo=ZoneInfo("Asia/Jakarta")),
                        )
                    self.assertEqual(rejected.exception.status_code, 404)
                    self.assertTrue(all(call.args[0].lstrip().startswith("SELECT")
                                        for call in cursor.execute.call_args_list))

    def test_permit_and_sick_require_nonempty_trimmed_reason(self):
        for status in ("permit", "sick"):
            with self.subTest(status=status), self.assertRaises(ManualAttendanceError):
                validate_manual_status_input(status, "  ")
        self.assertEqual(validate_manual_status_input("permit", " Izin keluarga "),
                         ("permit", "Izin keluarga"))
        self.assertEqual(validate_manual_status_input("sick", "Sakit"), ("sick", "Sakit"))

    def test_absent_note_is_optional_and_note_length_is_bounded(self):
        self.assertEqual(validate_manual_status_input("absent", "  "), ("absent", None))
        with self.assertRaises(ManualAttendanceError):
            validate_manual_status_input("permit", "x" * 501)

    def test_status_input_rejects_unknown_or_non_string_values(self):
        for status in (None, "present", "late", "holiday", "clear"):
            with self.subTest(status=status), self.assertRaises(ManualAttendanceError):
                validate_manual_status_input(status, "alasan")


class TeacherManualStatusRouteTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app({"TESTING": True, "SECRET_KEY": "manual-status-test"})
        self.client = self.app.test_client()
        password_hash = generate_password_hash("ManualStatusPass123!")
        self.teacher = {"id": 940, "username": "manual-teacher", "password_hash": password_hash,
                        "role": "teacher", "is_active": 1, "must_change_password": 0}
        self.student = {"id": 941, "username": "manual-student", "password_hash": password_hash,
                        "role": "student", "is_active": 1, "must_change_password": 0,
                        "face_registered": 1}

    def login(self, user):
        with self.app.app_context(), self.client.session_transaction() as session:
            session["user_id"] = user["id"]
            session["credential_stamp"] = credential_stamp(user["password_hash"])
            session["_csrf_token"] = "manual-status-csrf"

    def _active_user(self, user):
        return patch("app.services.auth_service.fetch_active_user", return_value=user)

    def test_manual_status_post_requires_teacher_and_csrf(self):
        path = "/teacher/students/841/manual-status"
        self.login(self.student)
        with self._active_user(self.student):
            forbidden = self.client.post(path, data={"class_id": "12", "status": "permit",
                                                     "notes": "alasan",
                                                     "csrf_token": "manual-status-csrf"})
        self.assertEqual(forbidden.status_code, 403)

        self.login(self.teacher)
        with self._active_user(self.teacher):
            missing_csrf = self.client.post(path, data={"class_id": "12", "status": "permit",
                                                       "notes": "alasan"})
        self.assertEqual(missing_csrf.status_code, 400)

    def test_success_posts_server_owned_today_and_redirects_to_detail(self):
        self.login(self.teacher)
        with self._active_user(self.teacher), patch(
                "app.teacher.routes.set_manual_attendance_status", return_value={"action": "created"}) as write:
            response = self.client.post(
                "/teacher/students/841/manual-status",
                data={"csrf_token": "manual-status-csrf", "class_id": "12",
                      "status": "permit", "notes": "Urusan keluarga"},
            )
        self.assertEqual(response.status_code, 302)
        self.assertIn("/teacher/students/841?", response.headers["Location"])
        write.assert_called_once_with(teacher_user_id=self.teacher["id"], student_id=841,
                                      class_value="12", status_value="permit",
                                      notes_value="Urusan keluarga")

    def test_out_of_scope_teacher_request_is_not_found(self):
        self.login(self.teacher)
        with self._active_user(self.teacher), patch(
                "app.teacher.routes.set_manual_attendance_status",
                side_effect=ManualAttendanceError("Siswa tidak ditemukan.", 404)):
            response = self.client.post(
                "/teacher/students/841/manual-status",
                data={"csrf_token": "manual-status-csrf", "class_id": "999",
                      "status": "absent"},
            )
        self.assertEqual(response.status_code, 404)


if __name__ == "__main__":
    unittest.main()
