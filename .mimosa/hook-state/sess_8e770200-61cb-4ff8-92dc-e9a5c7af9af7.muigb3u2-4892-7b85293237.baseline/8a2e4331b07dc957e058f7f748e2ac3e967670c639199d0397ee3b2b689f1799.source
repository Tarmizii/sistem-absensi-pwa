"""Admin export safety and audit-log route contract (T26)."""

from __future__ import annotations

from io import BytesIO
import unittest
from unittest.mock import patch

from openpyxl import load_workbook
from pymysql import MySQLError

from app import create_app
from app.services.attendance_read_service import AttendanceReadError
from app.services.auth_service import credential_stamp


class AdminExportsAuditRouteTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app({"TESTING": True, "SECRET_KEY": "admin-export-test"})
        self.client = self.app.test_client()
        self.admin = {"id": 971, "username": "admin-export", "password_hash": "hash",
                      "role": "admin", "is_active": 1, "must_change_password": 0}
        self.teacher = {**self.admin, "id": 972, "username": "teacher-export", "role": "teacher"}

    def login(self, user):
        with self.app.app_context(), self.client.session_transaction() as session:
            session["user_id"] = user["id"]
            session["credential_stamp"] = credential_stamp(user["password_hash"])
            session["_csrf_token"] = "admin-export-csrf"

    def active_user(self, user):
        return patch("app.services.auth_service.fetch_active_user", return_value=user)

    def test_export_and_audit_routes_require_admin_even_by_direct_url(self):
        self.login(self.teacher)
        with self.active_user(self.teacher):
            export = self.client.get("/admin/attendance/export.xlsx")
            audit = self.client.get("/admin/audit-logs")
        self.assertEqual(export.status_code, 403)
        self.assertEqual(audit.status_code, 403)

    def test_export_uses_journal_filters_and_exports_all_rows_without_page_limit(self):
        self.login(self.admin)
        rows = [{
            "record_id": index, "date": "2026-09-24", "class_name": "X-1",
            "student_id": index, "full_name": f"Siswa {index}", "nisn": f"001234{index:04d}",
            "status_label": "Hadir", "source_label": "Sistem", "status": "present",
            "checkin_time": "07:00", "checkout_time": "15:00", "notes": None,
        } for index in range(1, 28)]
        with self.active_user(self.admin), \
                patch("app.admin.routes.get_admin_attendance_export", create=True,
                      return_value=rows) as reader:
            response = self.client.get(
                "/admin/attendance/export.xlsx?date=2026-09-24&class_id=8"
                "&status=present&q=Siswa"
            )
        self.assertEqual(response.status_code, 200)
        reader.assert_called_once_with("2026-09-24", "8", "present", "Siswa")
        self.assertIn("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                      response.content_type)
        self.assertIn("attachment", response.headers.get("Content-Disposition", ""))
        self.assertEqual(response.headers["Cache-Control"], "no-store")
        workbook = load_workbook(BytesIO(response.data), data_only=False)
        sheet = workbook.active
        self.assertEqual(sheet.max_row, 28)
        self.assertEqual(sheet.cell(28, 4).value, "Siswa 27")
        self.assertEqual(sheet.cell(1, 1).value, "Tanggal")

    def test_formula_like_database_text_is_saved_as_plain_text(self):
        self.login(self.admin)
        row = {
            "record_id": 1, "date": "2026-09-24", "class_name": "=1+1",
            "student_id": 1, "full_name": "\t=HYPERLINK(\"https://example.invalid\")",
            "nisn": "0012345678", "status_label": "Hadir", "source_label": "Sistem",
            "checkin_time": None, "checkout_time": None, "notes": "@SUM(A1:A2)",
        }
        with self.active_user(self.admin), \
                patch("app.admin.routes.get_admin_attendance_export", create=True,
                      return_value=[row]):
            response = self.client.get("/admin/attendance/export.xlsx?date=2026-09-24")
        self.assertEqual(response.status_code, 200)
        sheet = load_workbook(BytesIO(response.data), data_only=False).active
        for coordinate in ("B2", "D2", "I2"):
            self.assertNotEqual(sheet[coordinate].data_type, "f", coordinate)
            self.assertTrue(str(sheet[coordinate].value).startswith("'"), coordinate)
        headers = [cell.value for cell in sheet[1]]
        serialized_headers = " ".join(headers).lower()
        for forbidden in ("photo", "latitude", "longitude", "face_score", "liveness", "storage"):
            self.assertNotIn(forbidden, serialized_headers)

    def test_empty_export_still_produces_a_valid_workbook_with_headers(self):
        self.login(self.admin)
        with self.active_user(self.admin), \
                patch("app.admin.routes.get_admin_attendance_export", create=True,
                      return_value=[]):
            response = self.client.get("/admin/attendance/export.xlsx?date=2026-09-24")
        self.assertEqual(response.status_code, 200)
        sheet = load_workbook(BytesIO(response.data), data_only=False).active
        self.assertEqual(sheet.max_row, 1)
        self.assertEqual(sheet.cell(1, 1).value, "Tanggal")

    def test_invalid_export_filter_returns_bad_request(self):
        self.login(self.admin)
        with self.active_user(self.admin), \
                patch("app.admin.routes.get_admin_attendance_export", create=True,
                      side_effect=AttendanceReadError("Tanggal tidak valid.", 400)):
            response = self.client.get("/admin/attendance/export.xlsx?date=invalid")
        self.assertEqual(response.status_code, 400)

    def test_audit_log_uses_actor_time_action_filters_and_omits_metadata(self):
        self.login(self.admin)
        model = {
            "rows": [{"created_at": "2026-09-24 08:00", "actor_label": "Admin Uji",
                      "action": "attendance_manual_status_set", "target_type": "attendance_record",
                      "target_id": 45}],
            "actor": "Admin", "date_from": "2026-09-24", "date_to": "2026-09-24",
            "action": "attendance_manual_status_set", "page": 1, "pages": 1, "total": 1,
        }
        with self.active_user(self.admin), \
                patch("app.admin.routes.get_admin_audit_logs", create=True,
                      return_value=model) as reader:
            response = self.client.get(
                "/admin/audit-logs?actor=Admin&from=2026-09-24&to=2026-09-24"
                "&action=attendance_manual_status_set&page=1"
            )
        self.assertEqual(response.status_code, 200)
        reader.assert_called_once_with(
            "Admin", "2026-09-24", "2026-09-24", "attendance_manual_status_set", "1"
        )
        body = response.get_data(as_text=True)
        self.assertIn("Jejak aktivitas", body)
        self.assertIn("attendance manual status set", body)
        self.assertIn("Admin Uji", body)
        self.assertNotIn("metadata", body.lower())
        self.assertNotIn("storage_key", body.lower())

    def test_audit_empty_filter_state_is_explicit(self):
        self.login(self.admin)
        model = {"rows": [], "actor": "absent-actor", "date_from": "", "date_to": "",
                 "action": "", "actions": [], "page": 1, "pages": 0, "total": 0}
        with self.active_user(self.admin), \
                patch("app.admin.routes.get_admin_audit_logs", create=True, return_value=model):
            response = self.client.get("/admin/audit-logs?actor=absent-actor")
        self.assertEqual(response.status_code, 200)
        self.assertIn("Tidak ada aktivitas yang cocok", response.get_data(as_text=True))

    def test_audit_extreme_dates_return_bad_request_instead_of_server_error(self):
        self.login(self.admin)
        for query in ("from=0001-01-01", "to=9999-12-31"):
            with self.subTest(query=query), self.active_user(self.admin):
                response = self.client.get("/admin/audit-logs?" + query)
                self.assertEqual(response.status_code, 400)

    def test_audit_database_failure_has_retry_action_and_preserves_filters(self):
        self.login(self.admin)
        with self.active_user(self.admin), \
                patch("app.admin.routes.get_admin_audit_logs", create=True,
                      side_effect=MySQLError("database unavailable")):
            response = self.client.get("/admin/audit-logs?actor=Admin&from=2026-09-24")
        self.assertEqual(response.status_code, 503)
        body = response.get_data(as_text=True)
        self.assertIn("Coba muat ulang", body)
        self.assertIn("actor=Admin", body)
        self.assertEqual(response.headers["Cache-Control"], "no-store")


if __name__ == "__main__":
    unittest.main()
