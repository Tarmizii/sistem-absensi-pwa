"""T12 exception validation, precedence, holiday, and Admin access tests."""

from __future__ import annotations

import unittest
from datetime import date, time
from unittest.mock import patch

from app import create_app
from werkzeug.security import generate_password_hash
from app.services.auth_service import credential_stamp
from app.services.schedule_exception_service import (
    ScheduleExceptionError,
    _validate,
)
from app.services.schedule_service import can_checkout, evaluate_checkin, resolve_schedule


class _Cursor:
    def __init__(self, one_rows=(), all_rows=()):
        self.one_rows = list(one_rows)
        self.all_rows = list(all_rows)

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def execute(self, *_args):
        pass

    def fetchone(self):
        return self.one_rows.pop(0)

    def fetchall(self):
        return self.all_rows.pop(0)


class _DB:
    def __init__(self, cursor):
        self._cursor = cursor

    def cursor(self):
        return self._cursor


class ScheduleExceptionTests(unittest.TestCase):
    def _admin_client(self):
        app = create_app({"TESTING": True, "SECRET_KEY": "schedule-exception-test"})
        client = app.test_client()
        admin = {"id": 18, "username": "admin", "password_hash": generate_password_hash("synthetic-admin"),
                 "role": "admin", "is_active": 1, "must_change_password": 0}
        with app.app_context(), client.session_transaction() as session:
            session["user_id"] = admin["id"]
            session["credential_stamp"] = credential_stamp(admin["password_hash"])
        return app, client, admin

    def test_scope_date_type_and_partial_override_validation(self):
        result = _validate(
            academic_year_id=12, exception_date="2026-09-25", scope="class", class_id=4,
            exception_type="early_dismissal", checkin_start="", late_after="",
            checkin_cutoff="", checkout_start="14:00",
        )
        self.assertEqual(result[:5], (12, date(2026, 9, 25), "class", 4, "early_dismissal"))
        self.assertEqual(result[5]["checkout_start"], time(14))

    def test_rejects_invalid_scope_type_date_and_time_order(self):
        common = dict(academic_year_id=12, exception_date="2026-09-25", scope="school",
                     class_id=None, exception_type="exam", checkin_start="07:30",
                     late_after="07:15", checkin_cutoff="08:00", checkout_start="15:00")
        for changes in (
            {"scope": "class"}, {"exception_type": "unknown"},
            {"exception_date": "not-a-date"}, {"checkin_start": "08:01"},
        ):
            with self.subTest(changes=changes), self.assertRaises(ScheduleExceptionError):
                _validate(**(common | changes))

    def test_class_then_school_then_regular_fields_are_merged(self):
        cursor = _Cursor(
            one_rows=[{"start_date": date(2026, 7, 1), "end_date": date(2027, 6, 30)},
                      {"academic_year_id": 12}],
            all_rows=[[
                {"exception_id": 22, "scope": "class", "class_id": 4,
                 "exception_type": "early_dismissal", "checkin_start": "07:10",
                 "late_after": None, "checkin_cutoff": None, "checkout_start": "14:00"},
                {"exception_id": 21, "scope": "school", "class_id": None,
                 "exception_type": "exam", "checkin_start": "07:05",
                 "late_after": "07:20", "checkin_cutoff": None, "checkout_start": None},
            ]],
        )
        regular = {"schedule_id": 9, "academic_year_id": 12, "checkin_start": "07:00",
                   "late_after": "07:15", "checkin_cutoff": "08:00", "checkout_start": "15:00",
                   "is_active": 1}
        with patch("app.services.schedule_exception_service.get_db", return_value=_DB(cursor)), \
                patch("app.services.schedule_exception_service.resolve_regular_schedule", return_value=regular):
            effective = resolve_schedule(date(2026, 9, 25), 12, 4)
        self.assertEqual(effective["source"], "class")
        self.assertEqual(effective["exception_id"], 22)
        self.assertEqual(effective["checkin_start"], "07:10")
        self.assertEqual(effective["late_after"], "07:20")
        self.assertEqual(effective["checkout_start"], "14:00")
        self.assertFalse(effective["is_holiday"])

    def test_holiday_never_allows_checkin_or_checkout(self):
        cursor = _Cursor(
            one_rows=[{"start_date": date(2026, 7, 1), "end_date": date(2027, 6, 30)}],
            all_rows=[[
                {"exception_id": 23, "scope": "school", "class_id": None,
                 "exception_type": "holiday", "checkin_start": None,
                 "late_after": None, "checkin_cutoff": None, "checkout_start": None},
            ]],
        )
        with patch("app.services.schedule_exception_service.get_db", return_value=_DB(cursor)), \
                patch("app.services.schedule_exception_service.resolve_regular_schedule", return_value=None):
            effective = resolve_schedule(date(2026, 9, 25), 12)
        self.assertTrue(effective["is_holiday"])
        self.assertEqual(evaluate_checkin(effective, time(7))["state"], "holiday")
        self.assertFalse(can_checkout(effective, time(15)))

    def test_non_admin_cannot_open_exception_management(self):
        app = create_app({"TESTING": True, "SECRET_KEY": "schedule-exception-test"})
        client = app.test_client()
        teacher = {"id": 19, "username": "teacher.test", "password_hash": "synthetic",
                   "role": "teacher", "is_active": 1, "must_change_password": 0}
        from app.services.auth_service import credential_stamp
        with app.app_context(), client.session_transaction() as session:
            session["user_id"] = teacher["id"]
            session["credential_stamp"] = credential_stamp(teacher["password_hash"])
        with patch("app.services.auth_service.fetch_active_user", return_value=teacher):
            response = client.get("/admin/schedule-exceptions")
        self.assertEqual(response.status_code, 403)

    def test_admin_exception_form_renders(self):
        _app, client, admin = self._admin_client()
        years = [{"id": 12, "name": "2026/2027", "is_active": 1}]
        with patch("app.services.auth_service.fetch_active_user", return_value=admin), \
                patch("app.admin.routes.list_academic_years", return_value=years), \
                patch("app.admin.routes.list_classes", return_value=[]), \
                patch("app.admin.routes.list_schedule_exceptions", return_value=[]):
            response = client.get("/admin/schedule-exceptions")
        self.assertEqual(response.status_code, 200)
        body = response.get_data(as_text=True)
        self.assertIn("Exception jadwal", body)
        self.assertIn("Preview jadwal efektif", body)
        self.assertIn('name="csrf_token"', body)

    def test_admin_preview_uses_effective_schedule_resolver(self):
        _app, client, admin = self._admin_client()
        years = [{"id": 12, "name": "2026/2027", "is_active": 1}]
        effective = {"for_date": date(2026, 9, 25), "source": "class", "exception_type": "early_dismissal",
                     "is_holiday": False, "schedule_id": 9, "checkin_start": "07:00",
                     "late_after": "07:20", "checkin_cutoff": "08:00", "checkout_start": "14:00"}
        with patch("app.services.auth_service.fetch_active_user", return_value=admin), \
                patch("app.admin.routes.resolve_effective_schedule", return_value=effective) as resolver, \
                patch("app.admin.routes.list_academic_years", return_value=years), \
                patch("app.admin.routes.list_classes", return_value=[]), \
                patch("app.admin.routes.list_schedule_exceptions", return_value=[]):
            response = client.get("/admin/schedule-exceptions/preview?academic_year_id=12&exception_date=2026-09-25&class_id=4")
        self.assertEqual(response.status_code, 200)
        self.assertIn("14:00", response.get_data(as_text=True))
        resolver.assert_called_once_with(date(2026, 9, 25), 12, 4)


if __name__ == "__main__":
    unittest.main()
