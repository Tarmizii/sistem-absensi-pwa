"""Read-only Guru monitoring pages with assignment-scoped access (T22)."""

from __future__ import annotations

from flask import Blueprint, abort, flash, g, redirect, render_template, request, url_for
from pymysql import MySQLError

from app.services.attendance_read_service import (
    AttendanceReadError,
    get_teacher_attendance,
    get_teacher_student_detail,
    get_teacher_students,
)
from app.services.auth_service import roles_required
from app.services.schedule_service import application_now
from app.services.manual_attendance_service import (
    ManualAttendanceError,
    set_manual_attendance_status,
)


teacher_bp = Blueprint("teacher", __name__)


def _render_read(template: str, reader, **params):
    try:
        model = reader(g.current_user["id"], **params)
    except AttendanceReadError as error:
        abort(error.status_code, description=str(error))
    except MySQLError:
        endpoint = request.endpoint or "role.teacher_dashboard"
        retry_params = dict(request.view_args or {})
        retry_params.update(request.args.to_dict(flat=True))
        return render_template("teacher/error.html", retry_url=url_for(endpoint, **retry_params)), 503
    return render_template(template, model=model)


@teacher_bp.get("/teacher/attendance")
@roles_required("teacher")
def attendance():
    return _render_read(
        "teacher/attendance.html", get_teacher_attendance,
        class_value=request.args.get("class_id"),
        month_value=request.args.get("month") or application_now().strftime("%Y-%m"),
        status_value=request.args.get("status"), query=request.args.get("q"),
        page_value=request.args.get("page"),
    )


@teacher_bp.get("/teacher/students")
@roles_required("teacher")
def students():
    return _render_read(
        "teacher/students.html", get_teacher_students,
        class_value=request.args.get("class_id"), query=request.args.get("q"),
        page_value=request.args.get("page"),
    )


@teacher_bp.get("/teacher/students/<int:student_id>")
@roles_required("teacher")
def student_detail(student_id: int):
    return _render_read(
        "teacher/student_detail.html", get_teacher_student_detail,
        class_value=request.args.get("class_id"), student_id=student_id,
        month_value=request.args.get("month"), selected_value=request.args.get("date"),
    )


@teacher_bp.post("/teacher/students/<int:student_id>/manual-status")
@roles_required("teacher")
def student_manual_status(student_id: int):
    class_value = request.form.get("class_id")
    return_url = url_for(
        "teacher.student_detail", student_id=student_id, class_id=class_value,
        month=application_now().strftime("%Y-%m"), date=application_now().date().isoformat(),
        source="manual",
    )
    try:
        outcome = set_manual_attendance_status(
            teacher_user_id=g.current_user["id"], student_id=student_id,
            class_value=class_value, status_value=request.form.get("status"),
            notes_value=request.form.get("notes", ""),
        )
    except ManualAttendanceError as error:
        if error.status_code == 404:
            abort(404, description=str(error))
        if error.status_code >= 500:
            abort(error.status_code, description="Status presensi belum dapat disimpan. Coba lagi.")
        flash(str(error), "error")
    except MySQLError:
        abort(503, description="Status presensi belum dapat disimpan. Coba lagi.")
    else:
        message = {
            "created": "Status presensi manual berhasil dicatat.",
            "corrected": "Status presensi berhasil diperbarui.",
            "cancelled": "Status manual berhasil dibatalkan.",
        }.get(outcome["action"], "Status presensi berhasil disimpan.")
        flash(message, "success")
    return redirect(return_url)
