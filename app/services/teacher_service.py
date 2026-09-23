"""Admin-owned Teacher account and profile operations for T08."""

from __future__ import annotations

import secrets
from typing import Any

from pymysql import IntegrityError
from werkzeug.security import generate_password_hash

from app.database import get_db, transaction
from app.services.account_service import USERNAME_PATTERN
from app.services.audit_service import record_audit


TEACHER_NAME_MAX_LENGTH = 150
EMPLOYEE_NUMBER_MAX_LENGTH = 50
TEMPORARY_PASSWORD_BYTES = 18


class TeacherValidationError(ValueError):
    """Input cannot be used for a Teacher account/profile."""


class TeacherConflictError(TeacherValidationError):
    """Username or employee number already exists."""


class TeacherNotFoundError(TeacherValidationError):
    """The requested Teacher does not exist or is not a Teacher account."""


def validate_teacher_input(username: str, full_name: str, employee_number: str = "") -> tuple[str, str, str | None]:
    if not all(isinstance(value, str) for value in (username, full_name, employee_number)):
        raise TeacherValidationError("Data Guru harus berupa teks.")
    if any(any(ord(char) < 32 for char in value) for value in (username, full_name, employee_number)):
        raise TeacherValidationError("Data Guru tidak boleh mengandung karakter kontrol.")
    normalized_username = username.strip()
    normalized_name = " ".join(full_name.split())
    normalized_employee = " ".join(employee_number.split()) or None
    if not USERNAME_PATTERN.fullmatch(normalized_username):
        raise TeacherValidationError("Username hanya boleh berisi huruf, angka, titik, garis bawah, atau tanda hubung (3–100 karakter).")
    if not 2 <= len(normalized_name) <= TEACHER_NAME_MAX_LENGTH:
        raise TeacherValidationError("Nama lengkap Guru harus berisi 2–150 karakter.")
    if normalized_employee is not None and not 3 <= len(normalized_employee) <= EMPLOYEE_NUMBER_MAX_LENGTH:
        raise TeacherValidationError("NIP/NUPTK harus berisi 3–50 karakter jika diisi.")
    return normalized_username, normalized_name, normalized_employee


def _temporary_password() -> str:
    # URL-safe output is easy to transcribe and always exceeds the minimum.
    return secrets.token_urlsafe(TEMPORARY_PASSWORD_BYTES)


def _translate_integrity(error: IntegrityError) -> TeacherConflictError:
    text = str(error).lower()
    if "employee" in text or "uq_teachers_employee" in text:
        return TeacherConflictError("NIP/NUPTK sudah digunakan.")
    return TeacherConflictError("Username sudah digunakan.")


def list_teachers(search: str = "") -> list[dict[str, Any]]:
    term = " ".join(search.split())
    like = f"%{term}%"
    with get_db().cursor() as cursor:
        cursor.execute(
            """SELECT t.id AS teacher_id, t.user_id, t.full_name,
                      t.employee_number, u.username, u.is_active,
                      u.must_change_password
               FROM teachers AS t JOIN users AS u ON u.id = t.user_id
               WHERE (%s = '' OR t.full_name LIKE %s
                      OR COALESCE(t.employee_number, '') LIKE %s
                      OR u.username LIKE %s)
               ORDER BY t.full_name, t.id LIMIT 200""",
            (term, like, like, like),
        )
        return list(cursor.fetchall())


def get_teacher(teacher_id: int) -> dict[str, Any] | None:
    with get_db().cursor() as cursor:
        cursor.execute(
            """SELECT t.id AS teacher_id, t.user_id, t.full_name,
                      t.employee_number, u.username, u.is_active,
                      u.must_change_password
               FROM teachers AS t JOIN users AS u ON u.id = t.user_id
               WHERE t.id = %s AND u.role = 'teacher' LIMIT 1""",
            (teacher_id,),
        )
        return cursor.fetchone()


def create_teacher(*, actor_user_id: int, username: str, full_name: str,
                   employee_number: str = "") -> dict[str, Any]:
    username, full_name, employee_number = validate_teacher_input(
        username, full_name, employee_number
    )
    temporary_password = _temporary_password()
    try:
        with transaction() as (_, cursor):
            cursor.execute("SELECT id FROM users WHERE username = %s LIMIT 1", (username,))
            if cursor.fetchone() is not None:
                raise TeacherConflictError("Username sudah digunakan.")
            if employee_number is not None:
                cursor.execute("SELECT id FROM teachers WHERE employee_number = %s LIMIT 1", (employee_number,))
                if cursor.fetchone() is not None:
                    raise TeacherConflictError("NIP/NUPTK sudah digunakan.")
            cursor.execute(
                """INSERT INTO users
                   (username, password_hash, role, is_active, must_change_password)
                   VALUES (%s, %s, 'teacher', 1, 1)""",
                (username, generate_password_hash(temporary_password)),
            )
            user_id = int(cursor.lastrowid)
            cursor.execute(
                "INSERT INTO teachers (user_id, full_name, employee_number) VALUES (%s, %s, %s)",
                (user_id, full_name, employee_number),
            )
            teacher_id = int(cursor.lastrowid)
            record_audit(cursor, actor_user_id=actor_user_id, action="teacher_created",
                         target_type="teacher", target_id=teacher_id,
                         metadata={"must_change_password": True,
                                   "employee_number_present": employee_number is not None})
    except IntegrityError as error:
        raise _translate_integrity(error) from None
    return {"teacher_id": teacher_id, "user_id": user_id, "username": username,
            "full_name": full_name, "temporary_password": temporary_password}


def update_teacher(*, actor_user_id: int, teacher_id: int, full_name: str,
                   employee_number: str = "") -> dict[str, Any]:
    _, full_name, employee_number = validate_teacher_input("valid-user", full_name, employee_number)
    try:
        with transaction() as (_, cursor):
            cursor.execute("SELECT id, user_id FROM teachers WHERE id = %s FOR UPDATE", (teacher_id,))
            teacher = cursor.fetchone()
            if teacher is None:
                raise TeacherNotFoundError("Guru tidak ditemukan.")
            if employee_number is not None:
                cursor.execute("SELECT id FROM teachers WHERE employee_number = %s AND id <> %s LIMIT 1", (employee_number, teacher_id))
                if cursor.fetchone() is not None:
                    raise TeacherConflictError("NIP/NUPTK sudah digunakan.")
            cursor.execute("UPDATE teachers SET full_name = %s, employee_number = %s WHERE id = %s",
                           (full_name, employee_number, teacher_id))
            record_audit(cursor, actor_user_id=actor_user_id, action="teacher_updated",
                         target_type="teacher", target_id=teacher_id,
                         metadata={"fields": ["full_name", "employee_number"]})
    except IntegrityError as error:
        raise _translate_integrity(error) from None
    return get_teacher(teacher_id) or {"teacher_id": teacher_id, "full_name": full_name,
                                       "employee_number": employee_number}


def deactivate_teacher(*, actor_user_id: int, teacher_id: int) -> None:
    with transaction() as (_, cursor):
        cursor.execute(
            """SELECT t.user_id FROM teachers AS t JOIN users AS u ON u.id = t.user_id
               WHERE t.id = %s AND u.role = 'teacher' FOR UPDATE""",
            (teacher_id,),
        )
        teacher = cursor.fetchone()
        if teacher is None:
            raise TeacherNotFoundError("Guru tidak ditemukan.")
        if int(teacher["user_id"]) == int(actor_user_id):
            raise TeacherValidationError("Admin tidak dapat menonaktifkan akun sendiri.")
        cursor.execute("UPDATE users SET is_active = 0 WHERE id = %s AND is_active = 1", (teacher["user_id"],))
        if cursor.rowcount != 1:
            raise TeacherValidationError("Akun Guru sudah nonaktif.")
        record_audit(cursor, actor_user_id=actor_user_id, action="teacher_deactivated",
                     target_type="teacher", target_id=teacher_id,
                     metadata={"is_active": False})


def reset_teacher_password(*, actor_user_id: int, teacher_id: int) -> dict[str, str]:
    temporary_password = _temporary_password()
    with transaction() as (_, cursor):
        cursor.execute(
            """SELECT t.user_id, u.username FROM teachers AS t JOIN users AS u ON u.id = t.user_id
               WHERE t.id = %s AND u.role = 'teacher' FOR UPDATE""",
            (teacher_id,),
        )
        teacher = cursor.fetchone()
        if teacher is None:
            raise TeacherNotFoundError("Guru tidak ditemukan.")
        cursor.execute("UPDATE users SET password_hash = %s, must_change_password = 1 WHERE id = %s AND is_active = 1",
                       (generate_password_hash(temporary_password), teacher["user_id"]))
        if cursor.rowcount != 1:
            raise TeacherValidationError("Akun Guru nonaktif dan tidak dapat direset.")
        record_audit(cursor, actor_user_id=actor_user_id, action="teacher_password_reset",
                     target_type="teacher", target_id=teacher_id,
                     metadata={"must_change_password": True})
    return {"username": teacher["username"], "temporary_password": temporary_password}
