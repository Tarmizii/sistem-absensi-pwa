"""Derive one student's daily attendance state and its single CTA (T17).

Backend is the sole authority for time, date, effective schedule, record state,
and whether an action is available. The browser only renders what this module
returns: it never decides eligibility on its own.
"""

from __future__ import annotations

from datetime import date, datetime, time
from typing import Any

from app.database import get_db
from app.services.schedule_service import (
    application_now,
    database_datetime_to_local_time,
    evaluate_checkin,
    can_checkout,
    resolve_schedule,
)


# Stored statuses only. 'Belum Absen' is a derived UI state and 'Libur' comes
# from the schedule engine; neither is written to attendance_records (PRD 12).
STATUS_LABELS = {
    "present": "Hadir",
    "late": "Terlambat",
    "permit": "Izin",
    "sick": "Sakit",
    "absent": "Alpa",
}
STATUS_SOURCE_LABELS = {"system": "Sistem", "teacher": "Guru", "finalization_job": "Sistem"}

# CTA labels fixed by FR-STU-03.
CTA_LABELS = {
    "checkin": "Presensi Masuk",
    "waiting": None,  # built from checkout_start: "Pulang mulai HH:MM"
    "checkout": "Presensi Pulang",
    "done": "Presensi Selesai",
    "holiday": "Presensi Tidak Tersedia",
    "before_start": "Presensi Masuk",
    "after_cutoff": "Presensi Ditutup",
    "manual_status": "Presensi Tidak Tersedia",
    "schedule_changed": "Presensi Dicatat",
    "no_schedule": "Presensi Tidak Tersedia",
}


def _time_text(value: time | str | None) -> str | None:
    if value is None:
        return None
    if isinstance(value, time):
        return value.strftime("%H:%M")
    return str(value)[:5]


def _status_label(status: str | None) -> str | None:
    if status is None:
        return "Belum Absen"
    return STATUS_LABELS.get(status, status)


def determine_action(*, schedule: dict[str, Any] | None, record: dict[str, Any] | None,
                     at: datetime) -> dict[str, Any]:
    """Pure mapping from effective schedule + record to one CTA.

    No I/O here so boundaries are testable with a controlled clock.
    """

    schedule_view = None if schedule is None else {
        "for_date": str(schedule.get("for_date") or at.date()),
        "checkin_start": _time_text(schedule.get("checkin_start")),
        "late_after": _time_text(schedule.get("late_after")),
        "checkin_cutoff": _time_text(schedule.get("checkin_cutoff")),
        "checkout_start": _time_text(schedule.get("checkout_start")),
        "is_holiday": bool(schedule.get("is_holiday")),
        "source": schedule.get("source"),
    }
    status = record.get("status") if record else None
    status_source = record.get("status_source") if record else None
    status_label = _status_label(status)
    checkin_at = record.get("checkin_at") if record else None
    checkout_at = record.get("checkout_at") if record else None

    # Row exists but only a manual/teacher status, without any auto-presence.
    if record is not None and checkin_at is None and status is not None:
        return {
            "state": "manual_status", "cta_label": CTA_LABELS["manual_status"],
            "cta_enabled": False,
            "reason": f"Status hari ini sudah ditetapkan: {status_label}.",
            "status_today": status_label, "status_source": status_source,
            "schedule": schedule_view, "can_checkin": False, "can_checkout_now": False,
        }

    if checkout_at is not None:
        return {
            "state": "done", "cta_label": CTA_LABELS["done"], "cta_enabled": False,
            "reason": "Presensi hari ini sudah selesai.",
            "status_today": status_label, "status_source": status_source,
            "schedule": schedule_view, "can_checkin": False, "can_checkout_now": False,
        }

    if checkin_at is not None and (schedule is None or schedule.get("is_holiday")):
        return {
            "state": "schedule_changed", "cta_label": CTA_LABELS["schedule_changed"],
            "cta_enabled": False,
            "reason": "Presensi masuk sudah tersimpan. Jadwal hari ini tidak tersedia untuk tindakan berikutnya.",
            "status_today": status_label, "status_source": status_source,
            "schedule": schedule_view, "can_checkin": False, "can_checkout_now": False,
        }

    if schedule is None:
        return {
            "state": "no_schedule", "cta_label": CTA_LABELS["no_schedule"],
            "cta_enabled": False, "reason": "Tidak ada jadwal presensi untuk hari ini.",
            "status_today": None, "status_source": None,
            "schedule": None, "can_checkin": False, "can_checkout_now": False,
        }

    if schedule.get("is_holiday"):
        return {
            "state": "holiday", "cta_label": CTA_LABELS["holiday"],
            "cta_enabled": False, "reason": "Hari libur; presensi tidak diperlukan.",
            "status_today": "Libur", "status_source": None,
            "schedule": schedule_view, "can_checkin": False, "can_checkout_now": False,
        }

    if checkin_at is not None:
        open_checkout = can_checkout(schedule, at)
        if open_checkout:
            return {
                "state": "checkout", "cta_label": CTA_LABELS["checkout"], "cta_enabled": True,
                "reason": None, "status_today": status_label, "status_source": status_source,
                "schedule": schedule_view, "can_checkin": False, "can_checkout_now": True,
            }
        return {
            "state": "waiting", "cta_label": f"Pulang mulai {schedule_view['checkout_start']}",
            "cta_enabled": False,
            "reason": f"Presensi pulang dapat dilakukan mulai {schedule_view['checkout_start']}.",
            "status_today": status_label, "status_source": status_source,
            "schedule": schedule_view, "can_checkin": False, "can_checkout_now": False,
        }

    # No record yet: decide check-in eligibility from the effective schedule.
    evaluation = evaluate_checkin(schedule, at)
    if evaluation["state"] == "before_start":
        return {
            "state": "before_start", "cta_label": CTA_LABELS["before_start"],
            "cta_enabled": False,
            "reason": f"Presensi dibuka pukul {schedule_view['checkin_start']}.",
            "status_today": "Belum Absen", "status_source": None,
            "schedule": schedule_view, "can_checkin": False, "can_checkout_now": False,
        }
    if evaluation["state"] == "after_cutoff":
        return {
            "state": "after_cutoff", "cta_label": CTA_LABELS["after_cutoff"],
            "cta_enabled": False,
            "reason": f"Batas check-in hari ini pukul {schedule_view['checkin_cutoff']}.",
            "status_today": "Belum Absen", "status_source": None,
            "schedule": schedule_view, "can_checkin": False, "can_checkout_now": False,
        }
    # Allowed: server already decided on-time vs late (PRD 12).
    predicted = _status_label(evaluation["status"])
    return {
        "state": "checkin", "cta_label": CTA_LABELS["checkin"], "cta_enabled": True,
        "reason": None, "status_today": "Belum Absen", "status_source": None,
        "predicted_status": predicted,
        "schedule": schedule_view, "can_checkin": True, "can_checkout_now": False,
    }


def load_day_context(user_id: int, at: datetime | None = None) -> dict[str, Any]:
    """Load student, placement, record, and effective schedule for one date.

    Shared by the dashboard (T17) and the check-in submission (T18) so both
    read the same rows before deciding what may happen today.
    """

    moment = application_now() if at is None else at
    for_date = moment.date()

    with get_db().cursor() as cursor:
        cursor.execute(
            """SELECT s.id AS student_id, s.full_name, s.face_registered, s.model_path
               FROM students AS s
               JOIN users AS u ON u.id = s.user_id
               WHERE u.id = %s AND u.role = 'student' AND u.is_active = 1
               LIMIT 1""",
            (user_id,),
        )
        student = cursor.fetchone()
        if student is None:
            raise LookupError("Profil Siswa tidak ditemukan.")

        cursor.execute(
            """SELECT sce.class_id, c.name AS class_name, sce.academic_year_id
               FROM student_class_enrollments AS sce
               JOIN classes AS c ON c.id = sce.class_id
               JOIN academic_years AS ay ON ay.id = sce.academic_year_id
               WHERE sce.student_id = %s AND ay.start_date <= %s AND ay.end_date >= %s
                 AND ay.is_active = 1
               LIMIT 1""",
            (student["student_id"], for_date, for_date),
        )
        placement = cursor.fetchone()

        cursor.execute(
            """SELECT status, status_source, checkin_at, checkout_at, class_id
               FROM attendance_records
               WHERE student_id = %s AND attendance_date = %s
               LIMIT 1""",
            (student["student_id"], for_date),
        )
        record = cursor.fetchone()

    academic_year_id = placement["academic_year_id"] if placement else None
    class_id = placement["class_id"] if placement else None
    schedule = resolve_schedule(for_date, academic_year_id, class_id)
    state = determine_action(schedule=schedule, record=record, at=moment)
    return {
        "student": student, "placement": placement, "record": record,
        "schedule": schedule, "state": state, "class_id": class_id,
        "academic_year_id": academic_year_id,
        "for_date": for_date, "moment": moment,
    }


def get_student_day_state(user_id: int, at: datetime | None = None) -> dict[str, Any]:
    """Public dashboard view built on top of load_day_context."""

    context = load_day_context(user_id, at)
    student = context["student"]
    placement = context["placement"]
    return {
        "student_id": int(student["student_id"]),
        "full_name": student["full_name"],
        "face_registered": bool(student["face_registered"]),
        "class_name": placement["class_name"] if placement else None,
        "today": context["for_date"].isoformat(),
        "server_time": context["moment"].strftime("%H:%M"),
        "checkin_time": database_datetime_to_local_time(
            context["record"].get("checkin_at") if context["record"] else None
        ),
        "checkout_time": database_datetime_to_local_time(
            context["record"].get("checkout_at") if context["record"] else None
        ),
        "status_source_label": STATUS_SOURCE_LABELS.get(
            context["state"].get("status_source")
        ),
        **context["state"],
    }
