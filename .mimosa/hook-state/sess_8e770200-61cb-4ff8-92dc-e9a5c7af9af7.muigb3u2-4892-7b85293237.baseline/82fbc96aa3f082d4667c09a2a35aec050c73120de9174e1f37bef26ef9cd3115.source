"""Fast account tests that do not require a running MySQL service."""

from __future__ import annotations

import json
import unittest
from pathlib import Path
from unittest.mock import patch

from app.database import transaction
from app.services.account_service import create_admin_user
from werkzeug.security import check_password_hash


class FakeCursor:
    def __init__(self, existing_username: str | None = None) -> None:
        self.existing_username = existing_username
        self.lastrowid = 41
        self.executed: list[tuple[str, tuple[object, ...]]] = []
        self._next_result = None

    def execute(self, statement: str, params=()) -> None:
        self.executed.append((" ".join(statement.split()), tuple(params)))
        if statement.lstrip().upper().startswith("SELECT"):
            self._next_result = (
                {"id": 9} if self.existing_username is not None else None
            )

    def fetchone(self):
        return self._next_result


class TransactionCursor:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False


class TransactionConnection:
    def __init__(self) -> None:
        self.commits = 0
        self.rollbacks = 0

    def cursor(self):
        return TransactionCursor()

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1


class AccountSetupTests(unittest.TestCase):
    def test_fixture_contains_no_passwords(self) -> None:
        fixture_path = Path(__file__).parent / "fixtures" / "users.json"
        fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
        self.assertEqual(
            {item["role"] for item in fixture}, {"admin", "teacher", "student"}
        )
        self.assertTrue(all("password" not in item for item in fixture))

    def test_admin_password_is_hashed_and_query_is_parameterized(self) -> None:
        cursor = FakeCursor()
        user_id = create_admin_user(cursor, "  first.admin ", "a-secure-test-password")
        self.assertEqual(user_id, 41)
        insert_statement, insert_params = cursor.executed[-1]
        self.assertIn("VALUES (%s, %s, 'admin', 1, 0)", insert_statement)
        self.assertEqual(insert_params[0], "first.admin")
        self.assertNotEqual(insert_params[1], "a-secure-test-password")
        self.assertTrue(check_password_hash(insert_params[1], "a-secure-test-password"))

    def test_duplicate_username_is_rejected_before_insert(self) -> None:
        cursor = FakeCursor(existing_username="taken")
        with self.assertRaisesRegex(ValueError, "sudah digunakan"):
            create_admin_user(cursor, "taken", "a-secure-test-password")
        self.assertEqual(len(cursor.executed), 1)

    def test_weak_password_is_rejected_before_query(self) -> None:
        cursor = FakeCursor()
        with self.assertRaisesRegex(ValueError, "minimal"):
            create_admin_user(cursor, "admin", "short")
        self.assertEqual(cursor.executed, [])

    def test_transaction_commits_after_success(self) -> None:
        connection = TransactionConnection()
        with patch("app.database.get_db", return_value=connection):
            with transaction():
                pass
        self.assertEqual(connection.commits, 1)
        self.assertEqual(connection.rollbacks, 0)

    def test_transaction_rolls_back_after_failure(self) -> None:
        connection = TransactionConnection()
        with patch("app.database.get_db", return_value=connection):
            with self.assertRaisesRegex(RuntimeError, "synthetic failure"):
                with transaction():
                    raise RuntimeError("synthetic failure")
        self.assertEqual(connection.commits, 0)
        self.assertEqual(connection.rollbacks, 1)

    def test_schema_contains_users_contract(self) -> None:
        schema = (Path(__file__).parents[1] / "database" / "schema.sql").read_text(
            encoding="utf-8"
        )
        self.assertIn("CREATE TABLE IF NOT EXISTS users", schema)
        self.assertIn("UNIQUE KEY uq_users_username", schema)
        self.assertIn("ENUM('admin', 'teacher', 'student')", schema)
        self.assertIn("must_change_password", schema)
        self.assertIn("CREATE TABLE IF NOT EXISTS audit_logs", schema)
        self.assertIn("CONSTRAINT fk_audit_actor", schema)
        self.assertIn("CREATE TABLE IF NOT EXISTS teachers", schema)
        self.assertIn("UNIQUE KEY uq_teachers_user", schema)
        self.assertIn("CREATE TABLE IF NOT EXISTS students", schema)
        self.assertIn("UNIQUE KEY uq_students_user", schema)
        self.assertIn("UNIQUE KEY uq_students_nisn", schema)
        self.assertIn("face_registered", schema)
        self.assertIn("CREATE TABLE IF NOT EXISTS academic_years", schema)
        self.assertIn("UNIQUE KEY uq_academic_years_name", schema)
        self.assertIn("CREATE TABLE IF NOT EXISTS classes", schema)
        self.assertIn("UNIQUE KEY uq_classes_year_name", schema)
        self.assertIn("CREATE TABLE IF NOT EXISTS student_class_enrollments", schema)
        self.assertIn("UNIQUE KEY uq_enrollments_student_year", schema)
        self.assertIn("CREATE TABLE IF NOT EXISTS attendance_schedules", schema)
        self.assertIn("UNIQUE KEY uq_schedules_year_day", schema)
        self.assertIn("checkin_start", schema)
        self.assertIn("checkout_start", schema)


if __name__ == "__main__":
    unittest.main()
