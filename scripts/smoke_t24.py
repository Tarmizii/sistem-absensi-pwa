"""Smoke current-day manual Guru statuses and audit behavior against dev MySQL."""

from __future__ import annotations

from datetime import date, datetime
from concurrent.futures import ThreadPoolExecutor
import secrets
from threading import Barrier

from pymysql import OperationalError
from werkzeug.security import generate_password_hash

from app import create_app
from app.database import get_db, transaction
from app.services.auth_service import credential_stamp
from app.services.manual_attendance_service import (
    ManualAttendanceError,
    set_manual_attendance_status,
)
from app.services.finalization_service import _write_alpa
from app.services.schedule_service import application_now
from app.services.schedule_service import resolve_schedule


def _must_reject(**kwargs) -> int:
    try:
        set_manual_attendance_status(**kwargs)
    except ManualAttendanceError as error:
        return error.status_code
    raise AssertionError("Expected manual-status operation to be rejected.")


def _cleanup(user_ids: list[int], teacher_ids: list[int], student_ids: list[int],
             class_id: int | None, year_id: int | None,
             exception_id: int | None) -> None:
    if not user_ids:
        return
    with transaction() as (_, cursor):
        if class_id:
            cursor.execute("DELETE FROM attendance_day_snapshots WHERE class_id=%s", (class_id,))
        placeholders = ",".join(["%s"] * len(user_ids))
        cursor.execute(f"DELETE FROM audit_logs WHERE actor_user_id IN ({placeholders})", tuple(user_ids))
        if student_ids:
            student_placeholders = ",".join(["%s"] * len(student_ids))
            cursor.execute(
                """DELETE FROM audit_logs WHERE target_type='attendance_record'
                   AND target_id IN (
                     SELECT id FROM attendance_records
                     WHERE student_id IN (""" + student_placeholders + "))",
                tuple(student_ids),
            )
            cursor.execute(
                f"DELETE FROM attendance_records WHERE student_id IN ({student_placeholders})",
                tuple(student_ids),
            )
            cursor.execute(
                f"DELETE FROM student_class_enrollments WHERE student_id IN ({student_placeholders})",
                tuple(student_ids),
            )
            cursor.execute(f"DELETE FROM students WHERE id IN ({student_placeholders})", tuple(student_ids))
        if exception_id:
            cursor.execute("DELETE FROM schedule_exceptions WHERE id=%s", (exception_id,))
        if class_id:
            cursor.execute("DELETE FROM classes WHERE id=%s", (class_id,))
        if year_id:
            cursor.execute("DELETE FROM attendance_schedules WHERE academic_year_id=%s", (year_id,))
            cursor.execute("DELETE FROM academic_years WHERE id=%s", (year_id,))
        if teacher_ids:
            teacher_placeholders = ",".join(["%s"] * len(teacher_ids))
            cursor.execute(f"DELETE FROM teachers WHERE id IN ({teacher_placeholders})", tuple(teacher_ids))
        cursor.execute(f"DELETE FROM users WHERE id IN ({placeholders})", tuple(user_ids))


def _login(app, user_id: int, password_hash: str):
    client = app.test_client()
    with app.app_context(), client.session_transaction() as session:
        session["user_id"] = user_id
        session["credential_stamp"] = credential_stamp(password_hash)
        session["_csrf_token"] = secrets.token_urlsafe(24)
    return client


def main() -> None:
    app = create_app({"TESTING": True})
    if app.config["APP_ENV"] == "production":
        raise SystemExit("Smoke T24 hanya boleh memakai database development/test.")
    suffix = secrets.token_hex(4)
    password_hash = generate_password_hash(f"Synthetic-T24-{suffix}-password")
    user_ids: list[int] = []
    teacher_ids: list[int] = []
    student_ids: list[int] = []
    class_id = year_id = exception_id = None
    record_ids: list[int] = []
    with app.app_context():
        moment = application_now()
        today = moment.date()
        early = moment.replace(hour=0, minute=0, second=0, microsecond=0)
        after_cutoff = moment.replace(hour=0, minute=2, second=0, microsecond=0)
        with transaction() as (_, cursor):
            for role, name in (("teacher", "satu"), ("teacher", "dua"),
                               ("student", "utama"), ("student", "otomatis"),
                               ("student", "libur")):
                cursor.execute(
                    "INSERT INTO users (username,password_hash,role,is_active,must_change_password) VALUES (%s,%s,%s,1,0)",
                    (f"smoke-t24-{name}-{suffix}", password_hash, role),
                )
                user_ids.append(int(cursor.lastrowid))
            for index, user_id in enumerate(user_ids[:2]):
                cursor.execute(
                    "INSERT INTO teachers (user_id,full_name,employee_number) VALUES (%s,%s,%s)",
                    (user_id, f"Guru T24 {index} {suffix}", f"T24{suffix}{index}"),
                )
                teacher_ids.append(int(cursor.lastrowid))
            cursor.execute(
                "INSERT INTO academic_years (name,start_date,end_date,is_active) VALUES (%s,%s,%s,1)",
                (f"T24-{suffix}", date(today.year, 1, 1), date(today.year, 12, 31)),
            )
            year_id = int(cursor.lastrowid)
            cursor.execute(
                "INSERT INTO classes (academic_year_id,name,teacher_id,is_active) VALUES (%s,%s,%s,1)",
                (year_id, f"T24-{suffix}", teacher_ids[0]),
            )
            class_id = int(cursor.lastrowid)
            cursor.execute(
                """INSERT INTO attendance_schedules
                   (academic_year_id,day_of_week,checkin_start,late_after,checkin_cutoff,checkout_start,is_active)
                   VALUES (%s,%s,'00:00','00:01','00:01','00:03',1)""",
                (year_id, today.isoweekday()),
            )
            # A class override gives the smoke a known non-holiday schedule even
            # if a school-wide exception happens to exist on today's date.
            cursor.execute(
                """INSERT INTO schedule_exceptions
                   (academic_year_id,exception_date,scope,class_id,exception_type,
                    checkin_start,late_after,checkin_cutoff,checkout_start,is_active)
                   VALUES (%s,%s,'class',%s,'custom','00:00','00:01','00:01','00:03',1)""",
                (year_id, today, class_id),
            )
            exception_id = int(cursor.lastrowid)
            for index, user_id in enumerate(user_ids[2:]):
                cursor.execute(
                    "INSERT INTO students (user_id,nisn,full_name,face_registered) VALUES (%s,%s,%s,1)",
                    (user_id, f"T24{suffix}{index:02d}", f"Siswa T24 {index} {suffix}"),
                )
                student_id = int(cursor.lastrowid)
                student_ids.append(student_id)
                cursor.execute(
                    "INSERT INTO student_class_enrollments (student_id,academic_year_id,class_id) VALUES (%s,%s,%s)",
                    (student_id, year_id, class_id),
                )

        try:
            base = {"teacher_user_id": user_ids[0], "student_id": student_ids[0],
                    "class_value": str(class_id)}
            client = _login(app, user_ids[0], password_hash)
            detail = client.get(
                f"/teacher/students/{student_ids[0]}?class_id={class_id}"
                f"&month={today:%Y-%m}&date={today.isoformat()}"
            )
            assert detail.status_code == 200, detail.get_data(as_text=True)
            assert "Status manual" in detail.get_data(as_text=True)
            assert "Simpan status" in detail.get_data(as_text=True)
            result = set_manual_attendance_status(
                **base, status_value="permit", notes_value="Keterangan rahasia uji", at=early)
            record_ids.append(result["record_id"])
            assert result["action"] == "created"
            with get_db().cursor() as cursor:
                cursor.execute(
                    """SELECT requires_attendance,source FROM attendance_day_snapshots
                       WHERE class_id=%s AND attendance_date=%s""",
                    (class_id, today),
                )
                snapshot = cursor.fetchone()
                assert snapshot is not None and snapshot["requires_attendance"] == 1
                assert snapshot["source"] == "manual_status"
            same_record = set_manual_attendance_status(
                **base, status_value="sick", notes_value="Sakit uji", at=early)
            assert same_record["record_id"] == result["record_id"] and same_record["action"] == "corrected"
            assert _must_reject(**base, status_value="absent", notes_value="", at=early) == 409
            cleared = set_manual_attendance_status(
                **base, status_value="clear", notes_value="", at=early)
            assert cleared["action"] == "cancelled" and cleared["record_id"] == result["record_id"]
    
            # A finalization job result can be corrected, but remains the same row.
            with transaction() as (_, cursor):
                cursor.execute(
                    "UPDATE attendance_records SET status='absent',status_source='finalization_job' WHERE id=%s",
                    (result["record_id"],),
                )
            corrected_job = set_manual_attendance_status(
                **base, status_value="permit", notes_value="Konfirmasi izin", at=after_cutoff)
            assert corrected_job["action"] == "corrected" and corrected_job["record_id"] == result["record_id"]
            assert _must_reject(**base, status_value="clear", notes_value="", at=after_cutoff) == 409
    
            with get_db().cursor() as cursor:
                cursor.execute(
                    "SELECT action, metadata FROM audit_logs WHERE target_type='attendance_record' AND target_id=%s ORDER BY id",
                    (result["record_id"],),
                )
                audits = list(cursor.fetchall())
                cursor.execute("SELECT status,status_source,notes FROM attendance_records WHERE id=%s",
                               (result["record_id"],))
                saved = cursor.fetchone()
            assert [row["action"] for row in audits] == [
                "attendance_manual_status_set", "attendance_manual_status_corrected",
                "attendance_manual_status_cancelled", "attendance_manual_status_corrected",
            ]
            assert all("Keterangan rahasia uji" not in str(row["metadata"]) for row in audits)
            assert saved == {"status": "permit", "status_source": "teacher", "notes": "Konfirmasi izin"}

            # A current placement must not grant writes to an unscoped record.
            with transaction() as (_, cursor):
                cursor.execute("UPDATE attendance_records SET class_id=NULL WHERE id=%s",
                               (result["record_id"],))
            for action in ("permit", "clear"):
                assert _must_reject(
                    **base, status_value=action, notes_value="Alasan" if action == "permit" else "",
                    at=early,
                ) == 404
            with transaction() as (_, cursor):
                cursor.execute("SELECT status,notes,class_id FROM attendance_records WHERE id=%s",
                               (result["record_id"],))
                assert cursor.fetchone() == {
                    "status": "permit", "notes": "Konfirmasi izin", "class_id": None,
                }
                cursor.execute("UPDATE attendance_records SET class_id=%s WHERE id=%s",
                               (class_id, result["record_id"]))
    
            # Automatic check-in is never replaced by a teacher status.
            automatic_id = student_ids[1]
            with transaction() as (_, cursor):
                cursor.execute(
                    """INSERT INTO attendance_records
                       (student_id,class_id,attendance_date,status,status_source,checkin_at)
                       VALUES (%s,%s,%s,'present','system',UTC_TIMESTAMP(6))""",
                    (automatic_id, class_id, today),
                )
                record_ids.append(int(cursor.lastrowid))
            assert _must_reject(teacher_user_id=user_ids[0], student_id=automatic_id,
                                class_value=str(class_id), status_value="sick",
                                notes_value="Alasan", at=after_cutoff) == 409
            automatic_detail = client.get(
                f"/teacher/students/{automatic_id}?class_id={class_id}"
                f"&month={today:%Y-%m}&date={today.isoformat()}"
            )
            assert automatic_detail.status_code == 200
            assert "Presensi otomatis Hadir/Terlambat tidak dapat diubah." in automatic_detail.get_data(as_text=True)
    
            # Holiday and current-assignment changes are checked at write time.
            with transaction() as (_, cursor):
                cursor.execute("UPDATE schedule_exceptions SET exception_type='holiday' WHERE id=%s",
                               (exception_id,))
            assert _must_reject(teacher_user_id=user_ids[0], student_id=student_ids[2],
                                class_value=str(class_id), status_value="permit",
                                notes_value="Libur", at=early) == 409
            with transaction() as (_, cursor):
                cursor.execute("UPDATE schedule_exceptions SET exception_type='custom' WHERE id=%s",
                               (exception_id,))
            # Race one manual write against the same row-lock path used by the
            # Alpa job. Exactly one student/date row must remain; no result is
            # silently overwritten after either transaction has committed.
            race_student_id = student_ids[2]
            race_schedule = resolve_schedule(today, year_id, class_id)
            assert race_schedule is not None and not race_schedule.get("is_holiday")
            barrier = Barrier(2)

            def race_manual():
                with app.app_context():
                    barrier.wait(timeout=5)
                    try:
                        return set_manual_attendance_status(
                            teacher_user_id=user_ids[0], student_id=race_student_id,
                            class_value=str(class_id), status_value="permit",
                            notes_value="Race izin", at=after_cutoff,
                        )
                    except ManualAttendanceError as error:
                        return {"action": "conflict", "status_code": error.status_code}

            def race_finalizer():
                with app.app_context():
                    barrier.wait(timeout=5)
                    try:
                        return _write_alpa(
                            schedule=race_schedule, student_id=race_student_id,
                            academic_year_id=year_id, class_id=class_id,
                            for_date=today, at=after_cutoff,
                        )
                    except OperationalError as error:
                        if error.args and error.args[0] in {1205, 1213}:
                            return "skipped", "raced"
                        raise

            with ThreadPoolExecutor(max_workers=2) as executor:
                manual_future = executor.submit(race_manual)
                finalizer_future = executor.submit(race_finalizer)
                manual_outcome = manual_future.result(timeout=15)
                finalizer_outcome = finalizer_future.result(timeout=15)
            # End the fixture reader's repeatable-read snapshot before checking
            # commits made on the worker connections.
            get_db().commit()
            assert manual_outcome["action"] in {"created", "corrected", "conflict"}
            assert finalizer_outcome[0] in {"finalized", "skipped"}
            with get_db().cursor() as cursor:
                cursor.execute(
                    "SELECT id,status,status_source FROM attendance_records WHERE student_id=%s AND attendance_date=%s",
                    (race_student_id, today),
                )
                race_row = cursor.fetchone()
                cursor.execute(
                    "SELECT COUNT(*) AS total FROM audit_logs WHERE target_type='attendance_record' AND target_id=%s",
                    (race_row["id"],),
                )
                race_audit_count = int(cursor.fetchone()["total"])
            record_ids.append(int(race_row["id"]))
            assert race_row["status"] in {"permit", "absent"}
            assert race_row["status_source"] in {"teacher", "finalization_job"}
            assert race_audit_count >= 1

            with transaction() as (_, cursor):
                cursor.execute("UPDATE classes SET teacher_id=%s WHERE id=%s",
                               (teacher_ids[1], class_id))
            assert _must_reject(teacher_user_id=user_ids[0], student_id=student_ids[2],
                                class_value=str(class_id), status_value="permit",
                                notes_value="Tidak lagi wali", at=early) == 404
            reassigned = set_manual_attendance_status(
                teacher_user_id=user_ids[1], student_id=student_ids[2],
                class_value=str(class_id), status_value="permit", notes_value="Guru baru",
                at=early,
            )
            record_ids.append(reassigned["record_id"])
    
            print("T24 MySQL smoke PASS: notes, status transitions, cutoff, holiday, assignment, auto-presence, manual-vs-job race, audit and cleanup.")
        finally:
            _cleanup(user_ids, teacher_ids, student_ids, class_id, year_id, exception_id)


if __name__ == "__main__":
    main()
