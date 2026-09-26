"""Teacher-authored attendance status for the current Jakarta day (T24)."""

from __future__ import annotations

from datetime import datetime, time
from typing import Any

from pymysql import IntegrityError, OperationalError

from app.database import get_db, transaction
from app.services.audit_service import record_audit
from app.services.attendance_day_snapshot_service import ensure_day_snapshot
from app.services.schedule_service import application_now, resolve_schedule
from app.services.schedule_exception_service import ScheduleExceptionError


class ManualAttendanceError(ValueError):
    """Manual status cannot be applied to this student/date/schedule."""

    def __init__(self, message: str, status_code: int = 409) -> None:
        super().__init__(message)
        self.status_code = status_code


def validate_manual_status_input(status_value: Any,
                                 notes_value: Any) -> tuple[str, str | None]:
    """Normalize the small set of statuses teachers may record."""
    if not isinstance(status_value, str) or status_value not in {"permit", "sick", "absent"}:
        raise ManualAttendanceError("Status manual tidak valid.", 400)
    if notes_value is None:
        notes_value = ""
    if not isinstance(notes_value, str):
        raise ManualAttendanceError("Keterangan tidak valid.", 400)
    notes = notes_value.strip()
    if len(notes) > 500 or any(ord(char) < 32 and char not in "\t\n\r" for char in notes):
        raise ManualAttendanceError("Keterangan maksimal 500 karakter.", 400)
    if status_value in {"permit", "sick"} and not notes:
        raise ManualAttendanceError("Keterangan wajib diisi untuk status Izin atau Sakit.", 400)
    return status_value, notes or None


def _parse_class_id(value: Any) -> int:
    if (not isinstance(value, str) or not value or len(value) > 20
            or not value.isascii() or not value.isdecimal() or int(value) < 1):
        raise ManualAttendanceError("Kelas tidak valid.", 400)
    return int(value)


def _cutoff(schedule: dict[str, Any]) -> time:
    value = schedule.get("checkin_cutoff")
    if isinstance(value, time):
        return value
    try:
        return time.fromisoformat(str(value))
    except ValueError:
        raise ManualAttendanceError("Cutoff jadwal efektif tidak valid.", 503) from None


def _time_of(moment: datetime) -> time:
    return moment.timetz().replace(tzinfo=None)


def set_manual_attendance_status(*, teacher_user_id: int, student_id: int,
                                 class_value: str | None, status_value: Any,
                                 notes_value: Any = None,
                                 at: datetime | None = None) -> dict[str, Any]:
    """Create/correct/cancel today's manual status in one audited transaction.

    The unique student/date key arbitrates races with check-in and Alpa
    finalization. A locked existing row is re-read immediately before mutation.
    """
    class_id = _parse_class_id(class_value)
    clear = status_value == "clear"
    if clear:
        if notes_value not in (None, ""):
            raise ManualAttendanceError("Keterangan harus kosong saat membatalkan status.", 400)
        status = None
        notes = None
    else:
        status, notes = validate_manual_status_input(status_value, notes_value)

    moment = application_now() if at is None else at
    if not isinstance(moment, datetime) or moment.utcoffset() is None:
        raise ManualAttendanceError("Waktu aplikasi tidak valid.", 503)
    today = moment.date()
    now_time = _time_of(moment)

    try:
        with transaction() as (_, cursor):
            cursor.execute(
                """SELECT sce.academic_year_id, sce.class_id
                   FROM student_class_enrollments AS sce
                   JOIN students AS s ON s.id=sce.student_id
                   JOIN users AS su ON su.id=s.user_id
                   JOIN classes AS c ON c.id=sce.class_id
                   JOIN academic_years AS ay ON ay.id=sce.academic_year_id
                   JOIN teachers AS t ON t.id=c.teacher_id
                   JOIN users AS tu ON tu.id=t.user_id
                   WHERE s.id=%s AND sce.class_id=%s AND t.user_id=%s
                     AND su.role='student' AND su.is_active=1
                     AND tu.role='teacher' AND tu.is_active=1
                     AND c.is_active=1 AND ay.is_active=1
                     AND ay.start_date<=%s AND ay.end_date>=%s
                   LIMIT 1 FOR UPDATE""",
                (student_id, class_id, teacher_user_id, today, today),
            )
            scope = cursor.fetchone()
            if scope is None:
                raise ManualAttendanceError("Siswa tidak ditemukan pada kelas aktif yang ditugaskan.", 404)

            try:
                schedule = resolve_schedule(today, int(scope["academic_year_id"]), class_id)
            except ScheduleExceptionError as error:
                raise ManualAttendanceError("Jadwal hari ini belum dapat dipastikan.", 409) from error
            if schedule is None:
                raise ManualAttendanceError("Tidak ada jadwal presensi untuk hari ini.", 409)
            if schedule.get("is_holiday"):
                raise ManualAttendanceError("Status manual tidak dapat dicatat pada hari libur.", 409)

            if clear and now_time > _cutoff(schedule):
                raise ManualAttendanceError(
                    "Status Guru hanya dapat dibatalkan sebelum cutoff check-in.", 409)
            if status == "absent" and now_time <= _cutoff(schedule):
                raise ManualAttendanceError("Status Alpa hanya dapat dicatat setelah cutoff check-in.", 409)

            cursor.execute(
                """SELECT id, class_id, status, status_source, checkin_at, checkout_at
                   FROM attendance_records
                   WHERE student_id=%s AND attendance_date=%s
                   LIMIT 1 FOR UPDATE""", (student_id, today)
            )
            record = cursor.fetchone()
            previous_status = record["status"] if record is not None else None
            if record is not None:
                # Current placement does not grant write access to another
                # class's historical record, or to an unscoped legacy record.
                if record["class_id"] is None or int(record["class_id"]) != class_id:
                    raise ManualAttendanceError("Record presensi tidak ditemukan pada kelas ini.", 404)
                if record["checkin_at"] is not None or record["checkout_at"] is not None \
                        or record["status"] in {"present", "late"}:
                    raise ManualAttendanceError(
                        "Presensi otomatis Hadir/Terlambat tidak dapat diubah.", 409)
                if record["status"] is not None and record["status_source"] not in {
                    "teacher", "finalization_job"
                }:
                    raise ManualAttendanceError("Record presensi tidak dapat diubah.", 409)

            if clear:
                if (record is None or record["status_source"] != "teacher"
                        or record["status"] not in {"permit", "sick", "absent"}):
                    raise ManualAttendanceError(
                        "Hanya status manual Guru yang dapat dibatalkan.", 409)
                cursor.execute(
                    """UPDATE attendance_records
                       SET status=NULL, status_source=NULL, notes=NULL, updated_by=%s
                       WHERE id=%s AND status_source='teacher'
                         AND checkin_at IS NULL AND checkout_at IS NULL""",
                    (teacher_user_id, record["id"]),
                )
                if cursor.rowcount != 1:
                    raise ManualAttendanceError("Status berubah bersamaan. Muat ulang dan periksa lagi.", 409)
                record_id = int(record["id"])
                audit_action = "attendance_manual_status_cancelled"
                outcome_action = "cancelled"
            else:
                if record is None:
                    cursor.execute(
                        """INSERT INTO attendance_records
                           (student_id,class_id,attendance_date,status,status_source,notes,
                            created_by,updated_by)
                           VALUES (%s,%s,%s,%s,'teacher',%s,%s,%s)""",
                        (student_id, class_id, today, status, notes,
                         teacher_user_id, teacher_user_id),
                    )
                    record_id = int(cursor.lastrowid)
                else:
                    cursor.execute(
                        """UPDATE attendance_records
                           SET class_id=COALESCE(class_id,%s), status=%s,
                               status_source='teacher', notes=%s, updated_by=%s
                           WHERE id=%s AND checkin_at IS NULL AND checkout_at IS NULL
                             AND (status IS NULL OR status NOT IN ('present','late'))""",
                        (class_id, status, notes, teacher_user_id, record["id"]),
                    )
                    if cursor.rowcount != 1:
                        raise ManualAttendanceError("Presensi berubah bersamaan. Muat ulang dan periksa lagi.", 409)
                    record_id = int(record["id"])
                audit_action = (
                    "attendance_manual_status_corrected" if previous_status is not None
                    else "attendance_manual_status_set"
                )
                outcome_action = "corrected" if previous_status is not None else "created"

            record_audit(
                cursor, actor_user_id=teacher_user_id, action=audit_action,
                target_type="attendance_record", target_id=record_id,
                metadata={"previous_status": previous_status, "status": status},
            )
            ensure_day_snapshot(
                cursor, academic_year_id=int(scope["academic_year_id"]),
                class_id=class_id, for_date=today, schedule=schedule,
                source="manual_status",
            )
    except IntegrityError:
        raise ManualAttendanceError(
            "Presensi tercatat bersamaan. Muat ulang untuk memastikan status terbaru.", 409) from None
    except OperationalError as error:
        if error.args and error.args[0] in {1205, 1213}:
            raise ManualAttendanceError(
                "Presensi berubah bersamaan. Muat ulang dan periksa lagi.", 409) from None
        raise
    return {"record_id": record_id, "action": outcome_action, "status": status}
