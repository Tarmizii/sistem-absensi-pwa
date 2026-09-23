"""Minimal role-protected destinations used by T03 redirects."""

from __future__ import annotations

from flask import Blueprint, g, redirect, render_template, url_for

from app.services.auth_service import login_required, roles_required


role_bp = Blueprint("role", __name__)


def render_profile(role: str, role_label: str):
    return render_template(
        "auth/profile.html",
        role=role,
        role_label=role_label,
        username=g.current_user["username"],
        is_active=bool(g.current_user["is_active"]),
        must_change_password=bool(g.current_user["must_change_password"]),
    )


@role_bp.get("/admin/dashboard")
@roles_required("admin")
def admin_dashboard():
    return render_template(
        "auth/role_dashboard.html",
        role_label="Admin",
        role="admin",
        username=g.current_user["username"],
    )


@role_bp.get("/teacher/dashboard")
@roles_required("teacher")
def teacher_dashboard():
    return render_template(
        "auth/role_dashboard.html",
        role_label="Guru/Wali Kelas",
        role="teacher",
        username=g.current_user["username"],
    )


@role_bp.get("/student/dashboard")
@roles_required("student")
def student_dashboard():
    return render_template(
        "auth/role_dashboard.html",
        role_label="Siswa",
        role="student",
        username=g.current_user["username"],
    )


@role_bp.get("/admin/profile")
@roles_required("admin")
def admin_profile():
    return render_profile("admin", "Admin")


@role_bp.get("/teacher/profile")
@roles_required("teacher")
def teacher_profile():
    return render_profile("teacher", "Guru/Wali Kelas")


@role_bp.get("/student/profile")
@roles_required("student")
def student_profile():
    return render_profile("student", "Siswa")


@role_bp.get("/profile")
@login_required
def profile_redirect():
    """Provide one safe shortcut while keeping role-specific profile URLs."""

    return redirect(url_for(f"role.{g.current_user['role']}_profile"))
