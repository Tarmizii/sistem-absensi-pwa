"""T23 protected evidence route boundaries and privacy."""

from __future__ import annotations

from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from app import create_app
from app.services.attendance_read_service import AttendanceReadError, get_attendance_evidence_file
from app.services.auth_service import credential_stamp
from werkzeug.security import generate_password_hash


class AttendanceEvidenceRouteTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="t23-evidence-")
        self.app = create_app({"TESTING": True, "SECRET_KEY": "t23-evidence-test",
                               "STORAGE_ROOT": str(Path(self.temp.name) / "private")})
        self.client = self.app.test_client()
        password_hash = generate_password_hash("EvidenceTestPass123!")
        self.teacher = {"id": 930, "username": "evidence-teacher", "password_hash": password_hash,
                        "role": "teacher", "is_active": 1, "must_change_password": 0}
        self.admin = {"id": 931, "username": "evidence-admin", "password_hash": password_hash,
                      "role": "admin", "is_active": 1, "must_change_password": 0}
        self.student = {"id": 932, "username": "evidence-student", "password_hash": password_hash,
                        "role": "student", "is_active": 1, "must_change_password": 0,
                        "face_registered": 1}

    def tearDown(self):
        self.temp.cleanup()

    def login(self, user):
        with self.app.app_context(), self.client.session_transaction() as session:
            session["user_id"] = user["id"]
            session["credential_stamp"] = credential_stamp(user["password_hash"])

    def active_user(self, user):
        return patch("app.services.auth_service.fetch_active_user", return_value=user)

    def test_evidence_detail_requires_authentication(self):
        response = self.client.get("/attendance/42/evidence")
        self.assertEqual(response.status_code, 302)
        self.assertIn("/login", response.headers["Location"])

    def test_student_role_cannot_read_evidence(self):
        self.login(self.student)
        with self.active_user(self.student):
            response = self.client.get("/attendance/42/evidence")
        self.assertEqual(response.status_code, 403)

    def test_teacher_out_of_scope_record_is_not_found(self):
        self.login(self.teacher)
        with self.active_user(self.teacher), patch(
                "app.attendance.routes.get_attendance_evidence",
                side_effect=AttendanceReadError("Bukti tidak ditemukan.", 404)) as read:
            response = self.client.get("/attendance/42/evidence")
        self.assertEqual(response.status_code, 404)
        read.assert_called_once_with(user_id=self.teacher["id"], role="teacher", record_id=42)

    def test_teacher_detail_contains_safe_summary_and_never_coordinates(self):
        self.login(self.teacher)
        model = {
            "record_id": 42, "student_id": 83, "class_id": 12,
            "student_name": "Siswa Uji", "class_name": "X-1",
            "date": "2026-09-24", "status_label": "Hadir", "source_label": "Sistem",
            "checkin_time": "07:10", "checkout_time": None,
            "checkin_accuracy": "12.50", "checkout_accuracy": None,
            "has_checkin_photo": True, "has_checkout_photo": False,
            "checkin_location_available": True, "checkout_location_available": False,
        }
        with self.active_user(self.teacher), patch(
                "app.attendance.routes.get_attendance_evidence", return_value=model):
            response = self.client.get("/attendance/42/evidence")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["Cache-Control"], "no-store")
        body = response.get_data(as_text=True)
        self.assertIn("Siswa Uji", body)
        self.assertIn("12.50", body)
        self.assertIn("Lokasi diterima saat presensi", body)
        self.assertIn("/attendance/42/evidence/checkin/image", body)
        self.assertNotIn("latitude", body.lower())
        self.assertNotIn("longitude", body.lower())
        self.assertNotIn("face_score", body.lower())

    def test_admin_can_read_detail_but_cannot_supply_storage_path(self):
        self.login(self.admin)
        model = {"record_id": 42, "student_id": 83, "class_id": 12,
                 "student_name": "Siswa Uji", "class_name": "X-1",
                 "date": "2026-09-24", "status_label": "Izin", "source_label": "Guru",
                 "checkin_time": None, "checkout_time": None,
                 "checkin_accuracy": None, "checkout_accuracy": None,
                 "has_checkin_photo": False, "has_checkout_photo": False,
                 "checkin_location_available": False, "checkout_location_available": False}
        with self.active_user(self.admin), patch(
                "app.attendance.routes.get_attendance_evidence", return_value=model) as read:
            response = self.client.get("/attendance/42/evidence?path=../../secrets.yml")
        self.assertEqual(response.status_code, 200)
        read.assert_called_once_with(user_id=self.admin["id"], role="admin", record_id=42)

    def test_image_uses_record_lookup_and_returns_private_no_store_response(self):
        self.login(self.teacher)
        image_path = Path(self.temp.name) / "evidence.webp"
        image_path.write_bytes(b"RIFFsynthetic-webp")
        with self.active_user(self.teacher), patch(
                "app.attendance.routes.get_attendance_evidence_file", return_value=image_path) as read:
            response = self.client.get("/attendance/42/evidence/checkin/image?key=faces%2Fguess.png")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.mimetype, "image/webp")
        self.assertEqual(response.headers["Cache-Control"], "no-store")
        read.assert_called_once_with(user_id=self.teacher["id"], role="teacher",
                                     record_id=42, phase="checkin")
        response.close()

    def test_missing_photo_is_not_found_and_role_scope_is_rechecked(self):
        self.login(self.teacher)
        with self.active_user(self.teacher), patch(
                "app.attendance.routes.get_attendance_evidence_file",
                side_effect=AttendanceReadError("Bukti tidak tersedia.", 404)):
            response = self.client.get("/attendance/42/evidence/checkout/image")
        self.assertEqual(response.status_code, 404)

    def test_real_file_resolver_rejects_missing_malformed_and_other_category_keys(self):
        from unittest.mock import MagicMock

        for key in (None, "attendance/../../secret.webp", "faces/" + "a" * 32 + ".png",
                    "attendance/" + "a" * 32 + ".webp"):
            with self.subTest(key=key), self.app.app_context(), \
                    patch("app.services.attendance_read_service.get_db", return_value=MagicMock()), \
                    patch("app.services.attendance_read_service._authorized_evidence_row",
                          return_value={"checkin_photo": key}), \
                    self.assertRaises(AttendanceReadError) as rejected:
                get_attendance_evidence_file(user_id=930, role="teacher", record_id=42, phase="checkin")
            self.assertEqual(rejected.exception.status_code, 404)

    def test_logged_out_session_cannot_fetch_a_previously_authorized_image(self):
        self.login(self.teacher)
        with self.client.session_transaction() as session:
            session.clear()
        with patch("app.attendance.routes.get_attendance_evidence_file") as read:
            response = self.client.get("/attendance/42/evidence/checkin/image")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers["Cache-Control"], "no-store")
        read.assert_not_called()


if __name__ == "__main__":
    unittest.main()
