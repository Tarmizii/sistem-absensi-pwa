"""Exercise T20 finalization against the configured dev MySQL (AC-10 + job rules).

AC-10: school holiday -> the job creates no Alpa for that date.
Also proven: only active placements are candidates, auto-presence and manual
statuses are never overwritten, double runs are idempotent, before-cutoff runs
write nothing, and dry-run reports counts without writing.

Real MySQL rows, schedules, exceptions, and transactions; every fixture is
removed in the finally block (student_faces/records first because of FKs).
"""

from __future__ import annotations

from datetime import date, datetime
import secrets

from werkzeug.security import generate_password_hash

from app import create_app
from app.database import get_db, transaction
from app.services.finalization_service import finalize_alpa


def main() -> None:
    app = create_app({"TESTING": True})
    if app.config["APP_ENV"] == "production":
        raise SystemExit("Smoke T20 tidak boleh dijalankan pada environment production.")
    sfx = secrets.token_hex(4)
    for_date = date.today()
    at_noon = datetime.combine(for_date, datetime.min.time()).replace(hour=12)
    at_early = datetime.combine(for_date, datetime.min.time()).replace(hour=7)
    password_hash = generate_password_hash("SmokeTest1234567!")
    user_ids: list[int] = []
    student_ids: list[int] = []
    seed: dict[str, int] = {}
    context = app.app_context()
    context.push()
    try:
        with transaction() as (_, cursor):
            cursor.execute(
                "INSERT INTO academic_years (name, start_date, end_date, is_active) VALUES (%s, %s, %s, 1)",
                (f"Tahun T20 {sfx}",
                 date.fromordinal(for_date.toordinal() - 7).isoformat(),
                 for_date.replace(year=for_date.year + 1).isoformat()))
            seed["year"] = int(cursor.lastrowid)
            cursor.execute(
                "INSERT INTO classes (academic_year_id, name, is_active) VALUES (%s, %s, 1)",
                (seed["year"], f"X-T20{sfx[:4]}"))
            seed["class"] = int(cursor.lastrowid)
            cursor.execute(
                "INSERT INTO attendance_schedules (academic_year_id, day_of_week, checkin_start, late_after, checkin_cutoff, checkout_start, is_active) VALUES (%s, %s, '06:30', '07:15', '08:00', '15:00', 1)",
                (seed["year"], for_date.isoweekday()))
            for label in ("hadir", "izin", "kosong"):
                cursor.execute(
                    "INSERT INTO users (username, password_hash, role, is_active) VALUES (%s, %s, 'student', 1)",
                    (f"smoke_t20_{label}_{sfx}", password_hash))
                user_id = int(cursor.lastrowid)
                user_ids.append(user_id)
                cursor.execute(
                    "INSERT INTO students (user_id, nisn, full_name, face_registered) VALUES (%s, %s, %s, 1)",
                    (user_id, f"93{sfx}{len(student_ids)}", f"Smoke T20 {label}"))
                student_id = int(cursor.lastrowid)
                student_ids.append(student_id)
                cursor.execute(
                    "INSERT INTO student_class_enrollments (student_id, academic_year_id, class_id) VALUES (%s, %s, %s)",
                    (student_id, seed["year"], seed["class"]))
            hadir_id, izin_id, kosong_id = student_ids
            cursor.execute(
                """INSERT INTO attendance_records
                   (student_id, class_id, attendance_date, status, status_source, checkin_at)
                   VALUES (%s, %s, %s, 'present', 'system', UTC_TIMESTAMP(6))""",
                (hadir_id, seed["class"], for_date))
            cursor.execute(
                """INSERT INTO attendance_records
                   (student_id, class_id, attendance_date, status, status_source)
                   VALUES (%s, %s, %s, 'permit', 'teacher')""",
                (izin_id, seed["class"], for_date))

        # Before cutoff: nothing is written.
        early = finalize_alpa(for_date=for_date, at=at_early)
        assert early["processed"] == 0, early
        assert early["skip_reasons"]["before_cutoff"] == 3, early
        print("before_cutoff=ok; no_write=ok")

        # After cutoff: only the student without any record becomes Alpa.
        after = finalize_alpa(for_date=for_date, at=at_noon)
        assert after["processed"] == 1, after
        assert after["skip_reasons"]["has_presence"] == 1, after
        assert after["skip_reasons"]["has_manual_status"] == 1, after
        with get_db().cursor() as cursor:
            cursor.execute(
                "SELECT status, status_source, checkin_at FROM attendance_records WHERE student_id=%s AND attendance_date=%s",
                (kosong_id, for_date))
            row = cursor.fetchone()
            assert row is not None and row["status"] == "absent", row
            assert row["status_source"] == "finalization_job", row
            assert row["checkin_at"] is None, row
            cursor.execute(
                "SELECT status FROM attendance_records WHERE student_id=%s AND attendance_date=%s",
                (hadir_id, for_date))
            assert cursor.fetchone()["status"] == "present", "presence overwritten"
            cursor.execute(
                "SELECT status FROM attendance_records WHERE student_id=%s AND attendance_date=%s",
                (izin_id, for_date))
            assert cursor.fetchone()["status"] == "permit", "manual status overwritten"
        print("after_cutoff=ok; presence_preserved=ok; manual_preserved=ok")

        # Double run: idempotent, no second write or audit.
        again = finalize_alpa(for_date=for_date, at=at_noon)
        assert again["processed"] == 0, again
        # hadir -> has_presence; izin + kosong (sudah Alpa) -> has_manual_status.
        assert again["skip_reasons"]["has_presence"] == 1, again
        assert again["skip_reasons"]["has_manual_status"] == 2, again
        with get_db().cursor() as cursor:
            cursor.execute(
                "SELECT COUNT(*) AS cnt FROM attendance_records WHERE student_id=%s AND attendance_date=%s",
                (kosong_id, for_date))
            assert cursor.fetchone()["cnt"] == 1, "duplicate record"
            cursor.execute(
                """SELECT COUNT(*) AS cnt FROM audit_logs
                   WHERE actor_user_id IS NULL AND action='attendance_alpa_finalized'
                     AND target_id=(SELECT id FROM attendance_records
                                    WHERE student_id=%s AND attendance_date=%s)""",
                (kosong_id, for_date))
            assert cursor.fetchone()["cnt"] == 1, "duplicate audit"
        print("double_run_idempotent=ok")

        # Dry run reports but does not touch rows already finalized.
        dry = finalize_alpa(for_date=for_date, at=at_noon, dry_run=True)
        assert dry["dry_run"] and dry["processed"] == 0, dry
        print("dry_run=ok")

        # AC-10: school holiday on another date -> zero Alpa.
        holiday_date = date.fromordinal(for_date.toordinal() - 1)
        with transaction() as (_, cursor):
            cursor.execute(
                """INSERT INTO schedule_exceptions
                   (academic_year_id, exception_date, scope, class_id, exception_type, is_active)
                   VALUES (%s, %s, 'school', NULL, 'holiday', 1)""",
                (seed["year"], holiday_date.isoformat()))
        holiday = finalize_alpa(
            for_date=holiday_date,
            at=datetime.combine(holiday_date, datetime.min.time()).replace(hour=16))
        assert holiday["processed"] == 0, holiday
        assert holiday["skip_reasons"]["holiday"] == 3, holiday
        with get_db().cursor() as cursor:
            cursor.execute(
                "SELECT COUNT(*) AS cnt FROM attendance_records WHERE attendance_date=%s",
                (holiday_date,))
            assert cursor.fetchone()["cnt"] == 0, "Alpa created on holiday"
            cursor.execute(
                "SELECT requires_attendance,source FROM attendance_day_snapshots WHERE class_id=%s AND attendance_date=%s",
                (seed["class"], for_date),
            )
            school_snapshot = cursor.fetchone()
            assert school_snapshot is not None and school_snapshot["requires_attendance"] == 1
            assert school_snapshot["source"] == "finalization_job"
            cursor.execute(
                "SELECT requires_attendance FROM attendance_day_snapshots WHERE class_id=%s AND attendance_date=%s",
                (seed["class"], holiday_date),
            )
            holiday_snapshot = cursor.fetchone()
            assert holiday_snapshot is not None and holiday_snapshot["requires_attendance"] == 0
        print("ac10_holiday_no_alpa=ok")

        print(f"t20_smoke=ok; ac10=ok; before_cutoff=ok; idempotent=ok; dry_run=ok; cleanup=ok")
    finally:
        try:
            with transaction() as (_, cursor):
                if student_ids:
                    ph = ",".join(["%s"] * len(student_ids))
                    ids = tuple(student_ids)
                    cursor.execute(
                        "DELETE FROM audit_logs WHERE actor_user_id IS NULL AND action='attendance_alpa_finalized'"
                        " AND target_id IN (SELECT id FROM attendance_records WHERE student_id IN (" + ph + "))",
                        ids)
                    cursor.execute(
                        "DELETE FROM student_faces WHERE student_id IN (" + ph + ")", ids)
                    cursor.execute(
                        "DELETE FROM attendance_records WHERE student_id IN (" + ph + ")", ids)
                    cursor.execute(
                        "DELETE FROM student_class_enrollments WHERE student_id IN (" + ph + ")", ids)
                    cursor.execute("DELETE FROM students WHERE id IN (" + ph + ")", ids)
                if user_ids:
                    ph = ",".join(["%s"] * len(user_ids))
                    ids = tuple(user_ids)
                    cursor.execute(
                        "DELETE FROM face_enrollment_challenges WHERE user_id IN (" + ph + ")", ids)
                    cursor.execute("DELETE FROM users WHERE id IN (" + ph + ")", ids)
                if seed:
                    cursor.execute(
                        "DELETE FROM attendance_day_snapshots WHERE class_id=%s",
                        (seed["class"],))
                    cursor.execute(
                        "DELETE FROM attendance_schedules WHERE academic_year_id=%s",
                        (seed["year"],))
                    cursor.execute(
                        "DELETE FROM schedule_exceptions WHERE academic_year_id=%s",
                        (seed["year"],))
                    cursor.execute("DELETE FROM classes WHERE academic_year_id=%s",
                                   (seed["year"],))
                    cursor.execute("DELETE FROM academic_years WHERE id=%s",
                                   (seed["year"],))
        finally:
            context.pop()


if __name__ == "__main__":
    main()
