"""Student-owned enrollment preparation page for T14."""

from __future__ import annotations

from flask import Blueprint, abort, g, redirect, render_template, url_for
from pymysql import MySQLError

from app.services.auth_service import roles_required
from app.services.enrollment_service import (
    StudentEnrollmentNotFoundError,
    get_own_enrollment_progress,
)


student_bp = Blueprint("student", __name__)


@student_bp.get("/student/enrollment")
@roles_required("student")
def enrollment():
    try:
        progress = get_own_enrollment_progress(g.current_user["id"])
    except StudentEnrollmentNotFoundError:
        abort(404)
    except MySQLError:
        return render_template("student/enrollment.html", progress=None,
                               database_unavailable=True), 503
    if progress["face_registered"]:
        return redirect(url_for("role.student_dashboard"))
    return render_template("student/enrollment.html", progress=progress,
                           database_unavailable=False)
