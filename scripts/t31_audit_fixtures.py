"""Synthetic fixtures for the T31 visual/accessibility audit.

Creates a small, isolated tenant (prefix ``audit.`` / NISN ``9926``) covering
every UI state the audit needs, plus a school-wide schedule exception for the
current day so the student CTA is exercisable on any weekday/weekend.

The shared account password comes from ``T31_AUDIT_PASSWORD`` when set;
otherwise a random dev-only value is generated. Credentials are written to
``instance/t31_audit_credentials.json`` (gitignored) instead of source control.

Usage:
    python -m scripts.t31_audit_fixtures            # create (idempotent)
    python -m scripts.t31_audit_fixtures --cleanup  # remove audit data
"""

from __future__ import annotations

import argparse
import json
import os
import secrets
from datetime import date, datetime
from pathlib import Path

from werkzeug.security import generate_password_hash

from app import create_app
from app.database import get_db, transaction
from app.services.account_service import create_admin_user
from app.services.class_service import create_class
from app.services.student_service import create_student
from app.services.teacher_service import create_teacher

AUDIT_PREFIX = "audit."
AUDIT_NISN_PREFIX = "9926"
AUDIT_CLASS_NAME = "AUDIT-T31"
ADMIN_USERNAME = "audit.admin"
TEACHER_USERNAME = "audit.guru"
CREDENTIALS_PATH = Path("instance") / "t31_audit_credentials.json"

# NISN -> desired state after fixtures run.
STUDENT_STATES = {
    "99260001": "fresh_password",      # must_change_password=1, no face
    "99260002": "enrollment_gate",     # password changed, face_registered=0
    "99260003": "ready",               # enrolled, no record today
    "99260004": "checked_in_present",  # check-in before late_after
    "99260005": "checked_in_late",     # check-in after late_after
    "99260006": "checked_out",         # check-in + check-out complete
    "99260007": "permit",              # teacher manual status Izin
    "99260008": "absent",              # finalization_job Alpa
}

STUDENT_NAMES = {
    "99260001": "Audit Baru Satu",
    "99260002": "Audit Enroll Dua",
    "99260003": "Audit Siap Tiga",
    "99260004": "Audit Hadir Empat",
    "99260005": "Audit Terlambat Lima",
    "99260006": "Audit Pulang Enam",
    "99260007": "Audit Izin Tujuh",
    "99260008": "Audit Alpa Delapan",
}


def _audit_password() -> str:
    """Environment override, else a fresh random dev-only value."""
    return os.getenv("T31_AUDIT_PASSWORD") or secrets.token_urlsafe(18)


def _save_credentials(payload: dict) -> None:
    CREDENTIALS_PATH.parent.mkdir(exist_ok=True)
    CREDENTIALS_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _load_credentials() -> dict:
    if CREDENTIALS_PATH.exists():
        return json.loads(CREDENTIALS_PATH.read_text(encoding="utf-8"))
    return {}


def _cleanup() -> None:
    with transaction() as (_, cursor):
        cursor.execute(
            "SELECT s.id, s.user_id FROM students AS s WHERE s.nisn LIKE %s",
            (AUDIT_NISN_PREFIX + "%",),
        )
        student_rows = cursor.fetchall()
        student_ids = [int(r["id"]) for r in student_rows]
        user_ids = [int(r["user_id"]) for r in student_rows]
        for nisn_code in STUDENT_STATES:
            cursor.execute(
                "SELECT u.id FROM users AS u WHERE u.username=%s", (nisn_code,)
            )
            row = cursor.fetchone()
            if row:
                user_ids.append(int(row["id"]))
        if student_ids:
            placeholders = ",".join(["%s"] * len(student_ids))
            cursor.execute(
                f"DELETE FROM attendance_records WHERE student_id IN ({placeholders})",
                tuple(student_ids),
            )
            cursor.execute(
                f"DELETE FROM student_faces WHERE student_id IN ({placeholders})",
                tuple(student_ids),
            )
            cursor.execute(
                f"DELETE FROM student_class_enrollments WHERE student_id IN ({placeholders})",
                tuple(student_ids),
            )
            cursor.execute(
                f"DELETE FROM students WHERE id IN ({placeholders})", tuple(student_ids)
            )
        cursor.execute(
            "SELECT t.id, t.user_id FROM teachers AS t JOIN users AS u ON u.id=t.user_id"
            " WHERE u.username LIKE %s OR u.username=%s",
            (AUDIT_PREFIX + "%", TEACHER_USERNAME),
        )
        teacher_rows = cursor.fetchall()
        for row in teacher_rows:
            cursor.execute(
                "UPDATE classes SET teacher_id=NULL WHERE teacher_id=%s", (row["id"],)
            )
            cursor.execute("DELETE FROM teachers WHERE id=%s", (row["id"],))
            user_ids.append(int(row["user_id"]))
        cursor.execute(
            "SELECT id FROM classes WHERE name=%s", (AUDIT_CLASS_NAME,)
        )
        class_row = cursor.fetchone()
        if class_row:
            class_id = int(class_row["id"])
            cursor.execute(
                "DELETE FROM attendance_day_snapshots WHERE class_id=%s", (class_id,)
            )
            cursor.execute(
                "DELETE FROM schedule_exceptions WHERE class_id=%s", (class_id,)
            )
            cursor.execute("DELETE FROM classes WHERE id=%s", (class_id,))
        cursor.execute(
            "SELECT id FROM users WHERE username LIKE %s OR username=%s",
            (AUDIT_PREFIX + "%", ADMIN_USERNAME),
        )
        for row in cursor.fetchall():
            user_ids.append(int(row["id"]))
        if user_ids:
            placeholders = ",".join(["%s"] * len(user_ids))
            cursor.execute(
                f"DELETE FROM audit_logs WHERE actor_user_id IN ({placeholders})",
                tuple(user_ids),
            )
            cursor.execute(
                f"DELETE FROM users WHERE id IN ({placeholders})", tuple(user_ids)
            )
        cursor.execute(
            """DELETE se FROM schedule_exceptions AS se
               WHERE se.exception_date=%s AND se.scope='school'
                 AND se.exception_type='custom'
                 AND se.checkin_start='00:00:00'""",
            (date.today(),),
        )
    if CREDENTIALS_PATH.exists():
        CREDENTIALS_PATH.unlink()
    print(json.dumps({"cleanup": "ok", "removed_students": len(student_rows)}))


def _seed_attendance(cursor, class_id: int, student_ids: dict[str, int]) -> None:
    today = date.today()
    now_utc = datetime.utcnow()

    def checkin_dt(late: bool) -> datetime:
        hour = (17 if late else 11) - 7  # WIB 17:05 / 11:05 stored as UTC
        return now_utc.replace(hour=hour, minute=5, second=0, microsecond=0)

    def checkout_dt() -> datetime:
        return now_utc.replace(hour=21 - 7, minute=10, second=0, microsecond=0)

    rows = [
        # (nisn, status, source, checkin, checkout, notes)
        ("99260004", "present", "system", checkin_dt(False), None, None),
        ("99260005", "late", "system", checkin_dt(True), None, None),
        ("99260006", "present", "system", checkin_dt(False), checkout_dt(), None),
        ("99260007", "permit", "teacher", None, None,
         "Audit fixture: izin keperluan keluarga"),
        ("99260008", "absent", "finalization_job", None, None, None),
    ]

    for nisn_code, status, source, checkin, checkout, notes in rows:
        cursor.execute(
            """INSERT INTO attendance_records
                 (student_id, class_id, attendance_date, status, status_source, notes,
                  checkin_at, checkout_at, checkin_liveness_verified,
                  checkin_latitude, checkin_longitude, checkin_accuracy)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,1,3.5294000,98.6630000,10.00)
               ON DUPLICATE KEY UPDATE status=VALUES(status),
                 status_source=VALUES(status_source), notes=VALUES(notes),
                 checkin_at=VALUES(checkin_at), checkout_at=VALUES(checkout_at)""",
            (student_ids[nisn_code], class_id, today, status, source, notes,
             checkin, checkout),
        )
        cursor.execute(
            """INSERT IGNORE INTO attendance_day_snapshots
                 (academic_year_id, class_id, attendance_date, requires_attendance, source)
               SELECT academic_year_id, %s, %s, 1, 'attendance_transaction'
               FROM classes WHERE id=%s""",
            (class_id, today, class_id),
        )


def _ensure_day_exception(cursor, academic_year_id: int) -> None:
    """Make today an attendance day (custom hours) even on weekends."""
    cursor.execute(
        """SELECT id FROM schedule_exceptions
           WHERE academic_year_id=%s AND exception_date=%s AND scope='school'""",
        (academic_year_id, date.today()),
    )
    existing = cursor.fetchone()
    if existing:
        return
    cursor.execute(
        """INSERT INTO schedule_exceptions
             (academic_year_id, exception_date, scope, class_id, exception_type,
              checkin_start, late_after, checkin_cutoff, checkout_start, is_active)
           VALUES (%s,%s,'school',NULL,'custom','00:00:00','23:00:00','23:59:00','23:59:00',1)""",
        (academic_year_id, date.today()),
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Fixture audit visual T31")
    parser.add_argument("--cleanup", action="store_true")
    args = parser.parse_args()

    app = create_app()
    with app.app_context():
        if args.cleanup:
            _cleanup()
            return 0

        stored = _load_credentials()
        password = stored.get("password") or _audit_password()
        summary: dict = {"accounts": {}, "students": {}, "password_source":
                         "env" if os.getenv("T31_AUDIT_PASSWORD")
                         else ("stored" if stored.get("password") else "generated")}

        with transaction() as (_, cursor):
            cursor.execute("SELECT id FROM users WHERE username=%s", (ADMIN_USERNAME,))
            row = cursor.fetchone()
            if row is None:
                admin_user_id = create_admin_user(cursor, ADMIN_USERNAME, password)
            else:
                admin_user_id = int(row["id"])
                cursor.execute(
                    "UPDATE users SET password_hash=%s, must_change_password=0"
                    " WHERE username=%s",
                    (generate_password_hash(password), ADMIN_USERNAME),
                )
        summary["accounts"]["admin"] = {"username": ADMIN_USERNAME, "user_id": admin_user_id}

        with get_db().cursor() as cursor:
            cursor.execute("SELECT id FROM academic_years WHERE is_active=1 LIMIT 1")
            academic_year_id = int(cursor.fetchone()["id"])

        with get_db().cursor() as cursor:
            cursor.execute(
                "SELECT t.id FROM teachers AS t JOIN users AS u ON u.id=t.user_id"
                " WHERE u.username=%s", (TEACHER_USERNAME,))
            teacher_row = cursor.fetchone()
        if teacher_row:
            teacher_id = int(teacher_row["id"])
        else:
            created = create_teacher(
                actor_user_id=admin_user_id, username=TEACHER_USERNAME,
                full_name="Audit Wali Kelas", employee_number="AUDIT-T31-001")
            teacher_id = int(created["teacher_id"])
        summary["accounts"]["teacher"] = {"username": TEACHER_USERNAME, "teacher_id": teacher_id}

        with get_db().cursor() as cursor:
            cursor.execute(
                "SELECT id FROM classes WHERE name=%s AND academic_year_id=%s",
                (AUDIT_CLASS_NAME, academic_year_id))
            class_row = cursor.fetchone()
        if class_row:
            class_id = int(class_row["id"])
        else:
            created = create_class(
                actor_user_id=admin_user_id, name=AUDIT_CLASS_NAME,
                academic_year_id=academic_year_id, teacher_id=teacher_id)
            class_id = int(created["class_id"])
        summary["class"] = {"name": AUDIT_CLASS_NAME, "id": class_id}
        summary["academic_year_id"] = academic_year_id

        student_ids: dict[str, int] = {}
        for nisn_code in STUDENT_STATES:
            with get_db().cursor() as cursor:
                cursor.execute("SELECT id FROM students WHERE nisn=%s", (nisn_code,))
                row = cursor.fetchone()
            if row:
                student_ids[nisn_code] = int(row["id"])
            else:
                created = create_student(
                    actor_user_id=admin_user_id, nisn=nisn_code,
                    full_name=STUDENT_NAMES[nisn_code])
                student_ids[nisn_code] = int(created["student_id"])
            summary["students"][nisn_code] = {
                "state": STUDENT_STATES[nisn_code], "username": nisn_code,
            }

        with transaction() as (_, cursor):
            for nisn_code, state in STUDENT_STATES.items():
                cursor.execute(
                    "SELECT s.user_id FROM students AS s WHERE s.nisn=%s", (nisn_code,))
                user_id = int(cursor.fetchone()["user_id"])
                keep_temp = state == "fresh_password"
                face_done = state not in {"fresh_password", "enrollment_gate"}
                cursor.execute(
                    "UPDATE users SET must_change_password=%s,"
                    " password_hash=%s WHERE id=%s",
                    (1 if keep_temp else 0,
                     generate_password_hash(password), user_id),
                )
                cursor.execute(
                    "UPDATE students SET face_registered=%s WHERE id=%s",
                    (1 if face_done else 0, student_ids[nisn_code]),
                )
                cursor.execute(
                    "SELECT id FROM student_class_enrollments WHERE student_id=%s"
                    " AND academic_year_id=%s",
                    (student_ids[nisn_code], academic_year_id))
                if cursor.fetchone() is None:
                    cursor.execute(
                        "INSERT INTO student_class_enrollments"
                        " (student_id, academic_year_id, class_id) VALUES (%s,%s,%s)",
                        (student_ids[nisn_code], academic_year_id, class_id))

            _seed_attendance(cursor, class_id, student_ids)
            _ensure_day_exception(cursor, academic_year_id)

        _save_credentials({"password": password, "summary": summary})
        summary["credentials_path"] = str(CREDENTIALS_PATH)
        summary.pop("password_source", None)
        print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
