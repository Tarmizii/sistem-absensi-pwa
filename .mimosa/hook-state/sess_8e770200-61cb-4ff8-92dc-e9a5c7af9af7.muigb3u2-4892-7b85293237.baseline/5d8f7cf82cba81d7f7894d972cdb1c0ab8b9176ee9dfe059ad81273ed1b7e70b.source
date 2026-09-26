"""Admin face reset endpoint for T16."""

from __future__ import annotations

import secrets
from contextlib import contextmanager
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch

from app import create_app
from app.database import get_db, transaction
from app.services.auth_service import credential_stamp
from app.services.student_service import reset_student_face, StudentValidationError, StudentNotFoundError
from werkzeug.security import generate_password_hash


_UNIQUE = secrets.token_hex(4)


def _suffix() -> str:
    return secrets.token_hex(4)


class AdminFaceResetServiceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="t16-reset-")
        self.app = create_app({"TESTING": True, "STORAGE_ROOT": str(Path(self.temp.name) / "private")})
        self.password_hash = generate_password_hash("TestPassword123!")
        self._cleanup_ids = []
        self.student_id = self._create_student()

    def tearDown(self):
        with self.app.app_context():
            for uid in reversed(self._cleanup_ids):
                try:
                    with transaction() as (_, cursor):
                        cursor.execute("DELETE FROM audit_logs WHERE actor_user_id=%s", (uid,))
                        cursor.execute("DELETE FROM student_faces WHERE student_id IN (SELECT id FROM students WHERE user_id=%s)", (uid,))
                        cursor.execute("DELETE FROM students WHERE user_id=%s", (uid,))
                        cursor.execute("DELETE FROM users WHERE id=%s", (uid,))
                except Exception:
                    pass
        self.temp.cleanup()

    def _create_student(self) -> int:
        suffix = secrets.token_hex(4)
        sfx = _suffix()
        with self.app.app_context(), transaction() as (_, cursor):
            cursor.execute(
                "INSERT INTO users (username, password_hash, role, is_active) VALUES (%s, %s, 'student', 1)",
                (f"t16svc_{suffix}", self.password_hash))
            user_id = cursor.lastrowid
            self._cleanup_ids.append(user_id)
            cursor.execute(
                "INSERT INTO students (user_id, nisn, full_name, face_registered) VALUES (%s, %s, 'Test Face', 1)",
                (user_id, f"90{suffix[:8]}"))
            student_id = cursor.lastrowid
            cursor.execute(
                "INSERT INTO student_faces (student_id, pose, storage_key) VALUES (%s, 'front', %s), (%s, 'left', %s), (%s, 'right', %s)",
                (student_id, f"faces/{sfx}f.png", student_id, f"faces/{sfx}l.png", student_id, f"faces/{sfx}r.png"))
            return student_id

    def test_reset_sets_face_registered_false_and_clears_faces(self):
        with self.app.app_context():
            actor_id = self._cleanup_ids[0]
            result = reset_student_face(actor_user_id=actor_id, student_id=self.student_id)
            self.assertIn("berhasil direset", result["message"])
            with get_db().cursor() as cursor:
                cursor.execute("SELECT face_registered, model_path FROM students WHERE id=%s", (self.student_id,))
                row = cursor.fetchone()
                self.assertFalse(row["face_registered"])
                self.assertIsNone(row["model_path"])
                cursor.execute("SELECT COUNT(*) AS cnt FROM student_faces WHERE student_id=%s", (self.student_id,))
                self.assertEqual(cursor.fetchone()["cnt"], 0)

    def test_reset_unregistered_student_is_rejected(self):
        with self.app.app_context(), transaction() as (_, cursor):
            suffix = secrets.token_hex(4)
            cursor.execute(
                "INSERT INTO users (username, password_hash, role, is_active) VALUES (%s, %s, 'student', 1)",
                (f"t16unreg_{suffix}", self.password_hash))
            user_id = cursor.lastrowid
            cursor.execute(
                "INSERT INTO students (user_id, nisn, full_name, face_registered) VALUES (%s, %s, 'No Face', 0)",
                (user_id, f"91{suffix[:8]}"))
            unreg_id = cursor.lastrowid
        with self.app.app_context():
            with self.assertRaises(StudentValidationError):
                reset_student_face(actor_user_id=user_id, student_id=unreg_id)

    def test_audit_log_created_on_reset(self):
        with self.app.app_context():
            reset_student_face(actor_user_id=self._cleanup_ids[0], student_id=self.student_id)
            with get_db().cursor() as cursor:
                cursor.execute(
                    "SELECT action FROM audit_logs WHERE target_type='student' AND target_id=%s ORDER BY id DESC LIMIT 1",
                    (self.student_id,))
                row = cursor.fetchone()
                self.assertEqual(row["action"], "face_reset")


class AdminFaceResetRouteTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="t16-reset-route-")
        self.app = create_app({"TESTING": True, "STORAGE_ROOT": str(Path(self.temp.name) / "private")})
        self.client = self.app.test_client()
        self.password_hash = generate_password_hash("TestPassword123!")
        self.csrf = "test-reset-csrf"
        self._admin_id, self._teacher_id = self._create_users()
        self._extra_user_ids = []

    def tearDown(self):
        with self.app.app_context():
            for uid in reversed(self._extra_user_ids + [self._teacher_id, self._admin_id]):
                try:
                    with transaction() as (_, cursor):
                        cursor.execute("DELETE FROM audit_logs WHERE actor_user_id=%s", (uid,))
                        cursor.execute("DELETE FROM student_faces WHERE student_id IN (SELECT id FROM students WHERE user_id=%s)", (uid,))
                        cursor.execute("DELETE FROM students WHERE user_id=%s", (uid,))
                        cursor.execute("DELETE FROM users WHERE id=%s", (uid,))
                except Exception:
                    pass
        self.temp.cleanup()

    def _create_users(self) -> tuple[int, int]:
        suffix = secrets.token_hex(4)
        with self.app.app_context(), transaction() as (_, cursor):
            cursor.execute(
                "INSERT INTO users (username, password_hash, role, is_active) VALUES (%s, %s, 'admin', 1)",
                (f"t16rte_adm_{suffix}", self.password_hash))
            admin_id = cursor.lastrowid
            cursor.execute(
                "INSERT INTO users (username, password_hash, role, is_active) VALUES (%s, %s, 'teacher', 1)",
                (f"t16rte_tch_{suffix}", self.password_hash))
            teacher_id = cursor.lastrowid
        return admin_id, teacher_id

    @contextmanager
    def _active_user(self, user_id: int, role: str):
        with self.app.app_context():
            with self.client.session_transaction() as session:
                session["user_id"] = user_id
                session["role"] = role
                session["credential_stamp"] = credential_stamp(self.password_hash)
                session["_csrf_token"] = self.csrf
            yield

    def test_non_admin_cannot_reset_face(self):
        with self._active_user(self._teacher_id, "teacher"):
            response = self.client.post(
                "/admin/students/999999/reset-face",
                headers={"X-CSRF-Token": self.csrf},
            )
        self.assertEqual(response.status_code, 403)

    def test_reset_face_redirects_with_flash(self):
        sfx = _suffix()
        with self.app.app_context(), transaction() as (_, cursor):
            cursor.execute(
                "INSERT INTO users (username, password_hash, role, is_active) VALUES (%s, %s, 'student', 1)",
                (f"t16rte_{sfx}", self.password_hash))
            uid = cursor.lastrowid
            self._extra_user_ids.append(uid)
            cursor.execute(
                "INSERT INTO students (user_id, nisn, full_name, face_registered) VALUES (%s, %s, 'Reset Route', 1)",
                (uid, f"92{sfx[:8]}"))
            sid = cursor.lastrowid
            cursor.execute(
                "INSERT INTO student_faces (student_id, pose, storage_key) VALUES (%s, 'front', %s)",
                (sid, f"faces/{sfx}r.png"))
        with self._active_user(self._admin_id, "admin"):
            response = self.client.post(
                f"/admin/students/{sid}/reset-face",
                headers={"X-CSRF-Token": self.csrf},
            )
        self.assertEqual(response.status_code, 302)
        self.assertIn("/admin/students/", response.headers["Location"])


if __name__ == "__main__":
    unittest.main()
