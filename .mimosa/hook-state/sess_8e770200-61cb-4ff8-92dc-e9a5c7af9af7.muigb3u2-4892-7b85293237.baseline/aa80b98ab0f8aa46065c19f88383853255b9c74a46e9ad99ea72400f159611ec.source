"""Admin master-data operations for academic years, classes, and placement."""

from __future__ import annotations

import re
from datetime import date
from typing import Any

from pymysql import IntegrityError

from app.database import get_db, transaction
from app.services.audit_service import record_audit


ACADEMIC_YEAR_NAME_PATTERN = re.compile(r"^[0-9]{4}/[0-9]{4}$")
CLASS_NAME_MAX_LENGTH = 80


class MasterDataValidationError(ValueError):
    """Master-data input is invalid or cannot be used."""


class MasterDataConflictError(MasterDataValidationError):
    """A unique master-data or placement constraint was violated."""


class MasterDataNotFoundError(MasterDataValidationError):
    """A referenced year, class, teacher, or student was not found."""


def _positive_id(value: Any, label: str) -> int:
    if type(value) is not int or value <= 0:
        raise MasterDataValidationError(f"{label} tidak valid.")
    return value


def validate_academic_year_input(name: str, start_date: str, end_date: str) -> tuple[str, date, date]:
    if not all(isinstance(value, str) for value in (name, start_date, end_date)):
        raise MasterDataValidationError("Data tahun ajaran harus berupa teks.")
    if any(any(ord(char) < 32 for char in value) for value in (name, start_date, end_date)):
        raise MasterDataValidationError("Data tahun ajaran tidak boleh mengandung karakter kontrol.")
    normalized_name = name.strip()
    if not ACADEMIC_YEAR_NAME_PATTERN.fullmatch(normalized_name):
        raise MasterDataValidationError("Tahun ajaran harus memakai format YYYY/YYYY.")
    try:
        start = date.fromisoformat(start_date.strip())
        end = date.fromisoformat(end_date.strip())
    except ValueError:
        raise MasterDataValidationError("Tanggal tahun ajaran harus memakai format YYYY-MM-DD.") from None
    if end < start:
        raise MasterDataValidationError("Tanggal selesai tidak boleh sebelum tanggal mulai.")
    return normalized_name, start, end


def validate_class_input(name: str, academic_year_id: int, teacher_id: int | None = None) -> tuple[str, int, int | None]:
    if not isinstance(name, str):
        raise MasterDataValidationError("Nama kelas harus berupa teks.")
    if any(ord(char) < 32 for char in name):
        raise MasterDataValidationError("Nama kelas tidak boleh mengandung karakter kontrol.")
    normalized_name = " ".join(name.split())
    if not 1 <= len(normalized_name) <= CLASS_NAME_MAX_LENGTH:
        raise MasterDataValidationError("Nama kelas harus berisi 1–80 karakter.")
    year_id = _positive_id(academic_year_id, "Tahun ajaran")
    normalized_teacher = None if teacher_id in (None, "", 0) else _positive_id(teacher_id, "Guru")
    return normalized_name, year_id, normalized_teacher


def _translate_integrity(error: IntegrityError) -> MasterDataConflictError:
    text = str(error).lower()
    if "uq_academic_years_name" in text or "academic_year" in text and "name" in text:
        return MasterDataConflictError("Nama tahun ajaran sudah digunakan.")
    if "uq_classes_year_name" in text or "classes" in text and "name" in text:
        return MasterDataConflictError("Nama kelas sudah digunakan pada tahun ajaran tersebut.")
    if "uq_enrollments_student_year" in text or "enrollment" in text:
        return MasterDataConflictError("Siswa sudah ditempatkan pada tahun ajaran tersebut.")
    return MasterDataConflictError("Data master bertabrakan dengan data yang sudah ada.")


def list_academic_years() -> list[dict[str, Any]]:
    with get_db().cursor() as cursor:
        cursor.execute(
            """SELECT id, name, start_date, end_date, is_active
               FROM academic_years ORDER BY start_date DESC, id DESC LIMIT 100"""
        )
        return list(cursor.fetchall())


def get_academic_year(academic_year_id: int) -> dict[str, Any] | None:
    with get_db().cursor() as cursor:
        cursor.execute("SELECT id, name, start_date, end_date, is_active FROM academic_years WHERE id=%s LIMIT 1", (academic_year_id,))
        return cursor.fetchone()


def create_academic_year(*, actor_user_id: int, name: str, start_date: str,
                         end_date: str, is_active: bool = False) -> dict[str, Any]:
    name, start, end = validate_academic_year_input(name, start_date, end_date)
    if type(is_active) is not bool:
        raise MasterDataValidationError("Status aktif tahun ajaran tidak valid.")
    try:
        with transaction() as (_, cursor):
            if is_active:
                cursor.execute("SELECT id FROM academic_years WHERE is_active=1")
                previous_active_ids = [int(row["id"]) for row in cursor.fetchall()]
                cursor.execute("UPDATE academic_years SET is_active=0 WHERE is_active=1")
                for previous_id in previous_active_ids:
                    record_audit(cursor, actor_user_id=actor_user_id, action="academic_year_deactivated",
                                 target_type="academic_year", target_id=previous_id,
                                 metadata={"is_active": False})
            cursor.execute(
                """INSERT INTO academic_years (name, start_date, end_date, is_active)
                   VALUES (%s, %s, %s, %s)""", (name, start, end, is_active)
            )
            year_id = int(cursor.lastrowid)
            record_audit(cursor, actor_user_id=actor_user_id, action="academic_year_created",
                         target_type="academic_year", target_id=year_id,
                         metadata={"is_active": is_active})
    except IntegrityError as error:
        raise _translate_integrity(error) from None
    return get_academic_year(year_id) or {"id": year_id, "name": name, "start_date": start, "end_date": end, "is_active": is_active}


def set_academic_year_active(*, actor_user_id: int, academic_year_id: int, is_active: bool) -> None:
    _positive_id(academic_year_id, "Tahun ajaran")
    if type(is_active) is not bool:
        raise MasterDataValidationError("Status aktif tahun ajaran tidak valid.")
    with transaction() as (_, cursor):
        cursor.execute("SELECT id, is_active FROM academic_years WHERE id=%s FOR UPDATE", (academic_year_id,))
        year = cursor.fetchone()
        if year is None:
            raise MasterDataNotFoundError("Tahun ajaran tidak ditemukan.")
        if is_active:
            cursor.execute("SELECT id FROM academic_years WHERE is_active=1 AND id<>%s FOR UPDATE", (academic_year_id,))
            previous_active_ids = [int(row["id"]) for row in cursor.fetchall()]
            cursor.execute("UPDATE academic_years SET is_active=0 WHERE is_active=1 AND id<>%s", (academic_year_id,))
            for previous_id in previous_active_ids:
                record_audit(cursor, actor_user_id=actor_user_id, action="academic_year_deactivated",
                             target_type="academic_year", target_id=previous_id,
                             metadata={"is_active": False})
        cursor.execute("UPDATE academic_years SET is_active=%s WHERE id=%s", (is_active, academic_year_id))
        if bool(year["is_active"]) != is_active:
            record_audit(cursor, actor_user_id=actor_user_id,
                         action="academic_year_activated" if is_active else "academic_year_deactivated",
                         target_type="academic_year", target_id=academic_year_id,
                         metadata={"is_active": is_active})


def list_classes(academic_year_id: int | None = None) -> list[dict[str, Any]]:
    params: tuple[Any, ...] = ()
    where = ""
    if academic_year_id is not None:
        _positive_id(academic_year_id, "Tahun ajaran")
        where = "WHERE c.academic_year_id = %s"
        params = (academic_year_id,)
    with get_db().cursor() as cursor:
        cursor.execute(
            f"""SELECT c.id AS class_id, c.academic_year_id, c.name, c.is_active,
                      ay.name AS academic_year_name, ay.start_date AS academic_year_start,
                      t.id AS teacher_id,
                      t.full_name AS teacher_name, COUNT(sce.id) AS student_count
               FROM classes AS c JOIN academic_years AS ay ON ay.id=c.academic_year_id
               LEFT JOIN teachers AS t ON t.id=c.teacher_id
               LEFT JOIN student_class_enrollments AS sce ON sce.class_id=c.id
               {where}
               GROUP BY c.id, c.academic_year_id, c.name, c.is_active,
                        ay.name, ay.start_date, t.id, t.full_name
               ORDER BY ay.start_date DESC, c.name, c.id LIMIT 200""", params
        )
        return list(cursor.fetchall())


def get_class(class_id: int) -> dict[str, Any] | None:
    with get_db().cursor() as cursor:
        cursor.execute(
            """SELECT c.id AS class_id, c.academic_year_id, c.name, c.is_active,
                      ay.name AS academic_year_name, ay.start_date AS academic_year_start,
                      t.id AS teacher_id,
                      t.full_name AS teacher_name, COUNT(sce.id) AS student_count
               FROM classes AS c JOIN academic_years AS ay ON ay.id=c.academic_year_id
               LEFT JOIN teachers AS t ON t.id=c.teacher_id
               LEFT JOIN student_class_enrollments AS sce ON sce.class_id=c.id
               WHERE c.id=%s GROUP BY c.id, c.academic_year_id, c.name, c.is_active,
                        ay.name, ay.start_date, t.id, t.full_name LIMIT 1""", (class_id,)
        )
        return cursor.fetchone()


def list_teacher_options() -> list[dict[str, Any]]:
    with get_db().cursor() as cursor:
        cursor.execute("""SELECT t.id AS teacher_id, t.full_name, u.username
                          FROM teachers AS t JOIN users AS u ON u.id=t.user_id
                          WHERE u.role='teacher' AND u.is_active=1
                          ORDER BY t.full_name, t.id LIMIT 200""")
        return list(cursor.fetchall())


def list_student_options(academic_year_id: int) -> list[dict[str, Any]]:
    _positive_id(academic_year_id, "Tahun ajaran")
    with get_db().cursor() as cursor:
        cursor.execute(
            """SELECT s.id AS student_id, s.nisn, s.full_name
               FROM students AS s JOIN users AS u ON u.id=s.user_id
               LEFT JOIN student_class_enrollments AS sce
                 ON sce.student_id=s.id AND sce.academic_year_id=%s
               WHERE u.role='student' AND u.is_active=1 AND sce.id IS NULL
               ORDER BY s.full_name, s.id LIMIT 500""", (academic_year_id,)
        )
        return list(cursor.fetchall())


def list_class_students(class_id: int) -> list[dict[str, Any]]:
    _positive_id(class_id, "Kelas")
    with get_db().cursor() as cursor:
        cursor.execute(
            """SELECT sce.id AS enrollment_id, s.id AS student_id, s.nisn, s.full_name,
                      sce.academic_year_id, sce.class_id
               FROM student_class_enrollments AS sce JOIN students AS s ON s.id=sce.student_id
               WHERE sce.class_id=%s ORDER BY s.full_name, s.id""", (class_id,)
        )
        return list(cursor.fetchall())


def create_class(*, actor_user_id: int, name: str, academic_year_id: int,
                 teacher_id: int | None = None) -> dict[str, Any]:
    name, year_id, teacher_id = validate_class_input(name, academic_year_id, teacher_id)
    try:
        with transaction() as (_, cursor):
            cursor.execute("SELECT id FROM academic_years WHERE id=%s LIMIT 1", (year_id,))
            if cursor.fetchone() is None:
                raise MasterDataNotFoundError("Tahun ajaran tidak ditemukan.")
            if teacher_id is not None:
                cursor.execute("""SELECT t.id FROM teachers AS t JOIN users AS u ON u.id=t.user_id
                                  WHERE t.id=%s AND u.role='teacher' AND u.is_active=1 LIMIT 1""", (teacher_id,))
                if cursor.fetchone() is None:
                    raise MasterDataNotFoundError("Guru aktif tidak ditemukan.")
            cursor.execute("INSERT INTO classes (academic_year_id, name, teacher_id, is_active) VALUES (%s,%s,%s,1)",
                           (year_id, name, teacher_id))
            class_id = int(cursor.lastrowid)
            record_audit(cursor, actor_user_id=actor_user_id, action="class_created",
                         target_type="class", target_id=class_id,
                         metadata={"teacher_assigned": teacher_id is not None})
    except IntegrityError as error:
        raise _translate_integrity(error) from None
    return get_class(class_id) or {"class_id": class_id, "academic_year_id": year_id, "name": name, "teacher_id": teacher_id}


def update_class(*, actor_user_id: int, class_id: int, name: str, teacher_id: int | None = None) -> dict[str, Any]:
    name, _, teacher_id = validate_class_input(name, 1, teacher_id)
    try:
        with transaction() as (_, cursor):
            cursor.execute("SELECT id, academic_year_id FROM classes WHERE id=%s FOR UPDATE", (class_id,))
            current = cursor.fetchone()
            if current is None:
                raise MasterDataNotFoundError("Kelas tidak ditemukan.")
            if teacher_id is not None:
                cursor.execute("""SELECT t.id FROM teachers AS t JOIN users AS u ON u.id=t.user_id
                                  WHERE t.id=%s AND u.role='teacher' AND u.is_active=1 LIMIT 1""", (teacher_id,))
                if cursor.fetchone() is None:
                    raise MasterDataNotFoundError("Guru aktif tidak ditemukan.")
            cursor.execute("UPDATE classes SET name=%s, teacher_id=%s WHERE id=%s", (name, teacher_id, class_id))
            record_audit(cursor, actor_user_id=actor_user_id, action="class_updated",
                         target_type="class", target_id=class_id,
                         metadata={"fields": ["name", "teacher_id"]})
    except IntegrityError as error:
        raise _translate_integrity(error) from None
    return get_class(class_id) or {"class_id": class_id, "name": name, "teacher_id": teacher_id}


def deactivate_class(*, actor_user_id: int, class_id: int) -> None:
    with transaction() as (_, cursor):
        cursor.execute("SELECT id FROM classes WHERE id=%s FOR UPDATE", (class_id,))
        if cursor.fetchone() is None:
            raise MasterDataNotFoundError("Kelas tidak ditemukan.")
        cursor.execute("UPDATE classes SET is_active=0 WHERE id=%s AND is_active=1", (class_id,))
        if cursor.rowcount != 1:
            raise MasterDataValidationError("Kelas sudah nonaktif.")
        record_audit(cursor, actor_user_id=actor_user_id, action="class_deactivated",
                     target_type="class", target_id=class_id, metadata={"is_active": False})


def assign_student(*, actor_user_id: int, class_id: int, student_id: int) -> dict[str, Any]:
    class_id = _positive_id(class_id, "Kelas")
    student_id = _positive_id(student_id, "Siswa")
    try:
        with transaction() as (_, cursor):
            cursor.execute("SELECT id, academic_year_id FROM classes WHERE id=%s AND is_active=1 FOR UPDATE", (class_id,))
            target_class = cursor.fetchone()
            if target_class is None:
                raise MasterDataNotFoundError("Kelas aktif tidak ditemukan.")
            cursor.execute("""SELECT s.id FROM students AS s JOIN users AS u ON u.id=s.user_id
                              WHERE s.id=%s AND u.role='student' AND u.is_active=1 LIMIT 1""", (student_id,))
            if cursor.fetchone() is None:
                raise MasterDataNotFoundError("Siswa aktif tidak ditemukan.")
            cursor.execute("SELECT id FROM student_class_enrollments WHERE student_id=%s AND academic_year_id=%s LIMIT 1",
                           (student_id, target_class["academic_year_id"]))
            if cursor.fetchone() is not None:
                raise MasterDataConflictError("Siswa sudah ditempatkan pada tahun ajaran tersebut.")
            cursor.execute("INSERT INTO student_class_enrollments (student_id, academic_year_id, class_id) VALUES (%s,%s,%s)",
                           (student_id, target_class["academic_year_id"], class_id))
            enrollment_id = int(cursor.lastrowid)
            record_audit(cursor, actor_user_id=actor_user_id, action="student_enrollment_created",
                         target_type="student_enrollment", target_id=enrollment_id,
                         metadata={"student_id_present": True, "class_id_present": True})
    except IntegrityError as error:
        raise _translate_integrity(error) from None
    return {"enrollment_id": enrollment_id, "student_id": student_id,
            "academic_year_id": target_class["academic_year_id"], "class_id": class_id}


def list_teacher_classes(teacher_user_id: int) -> list[dict[str, Any]]:
    teacher_user_id = _positive_id(teacher_user_id, "Akun Guru")
    with get_db().cursor() as cursor:
        cursor.execute(
            """SELECT c.id AS class_id, c.name, c.academic_year_id, ay.name AS academic_year_name,
                      ay.start_date AS academic_year_start,
                      c.is_active, COUNT(sce.id) AS student_count
               FROM classes AS c JOIN teachers AS t ON t.id=c.teacher_id
               JOIN users AS u ON u.id=t.user_id
               JOIN academic_years AS ay ON ay.id=c.academic_year_id
               LEFT JOIN student_class_enrollments AS sce ON sce.class_id=c.id
               WHERE t.user_id=%s AND u.role='teacher' AND u.is_active=1 AND c.is_active=1
               GROUP BY c.id, c.name, c.academic_year_id, ay.name, ay.start_date, c.is_active
               ORDER BY ay.start_date DESC, c.name""", (teacher_user_id,)
        )
        return list(cursor.fetchall())
