"""Login, logout, and password-change routes."""

from __future__ import annotations

from flask import (
    Blueprint,
    flash,
    g,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from pymysql import MySQLError
from werkzeug.security import check_password_hash

from app.services.auth_service import (
    MIN_ADMIN_PASSWORD_LENGTH,
    authenticate,
    clear_login_failures,
    credential_stamp,
    is_login_rate_limited,
    login_required,
    login_attempt_key,
    record_login_failure,
    update_password,
)
from app.services.csrf_service import issue_csrf_token


auth_bp = Blueprint("auth", __name__)


def role_dashboard_endpoint(role: str) -> str:
    """Map the three fixed roles to their initial dashboard endpoints."""

    return {
        "admin": "role.admin_dashboard",
        "teacher": "role.teacher_dashboard",
        "student": "role.student_dashboard",
    }[role]


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    """Authenticate one account with a generic failure message."""

    if g.get("current_user") is not None:
        return redirect(url_for(role_dashboard_endpoint(g.current_user["role"])))

    if request.method == "POST":
        attempt_key = login_attempt_key(
            request.form.get("username", ""), request.remote_addr
        )
        if is_login_rate_limited(attempt_key):
            flash("Terlalu banyak percobaan login. Coba lagi nanti.", "error")
            return render_template("auth/login.html"), 429
        try:
            user = authenticate(
                request.form.get("username", ""), request.form.get("password", "")
            )
        except MySQLError:
            flash("Layanan login belum tersedia. Coba lagi setelah database siap.", "error")
            return render_template("auth/login.html"), 503

        if user is None:
            record_login_failure(attempt_key)
            flash("Username atau password salah.", "error")
            return render_template("auth/login.html"), 401

        clear_login_failures(attempt_key)
        session.clear()
        session.permanent = True
        session["user_id"] = user["id"]
        session["credential_stamp"] = credential_stamp(user["password_hash"])
        session["role"] = user["role"]
        session["must_change_password"] = bool(user["must_change_password"])
        # Regenerate the token after clearing the pre-login session.
        issue_csrf_token()
        if user["must_change_password"]:
            return redirect(url_for("auth.change_password"))
        return redirect(url_for(role_dashboard_endpoint(user["role"])))

    return render_template("auth/login.html")


@auth_bp.post("/logout")
def logout():
    """End the current session; CSRF is enforced application-wide."""

    session.clear()
    flash("Anda sudah logout.", "success")
    return redirect(url_for("auth.login"))


@auth_bp.route("/change-password", methods=["GET", "POST"])
@login_required
def change_password():
    """Change a password, including the first forced change."""

    if request.method == "POST":
        current_password = request.form.get("current_password", "")
        new_password = request.form.get("new_password", "")
        confirmation = request.form.get("confirmation", "")
        user = g.current_user

        if not check_password_hash(user["password_hash"], current_password):
            flash("Password saat ini salah.", "error")
        elif len(new_password) < MIN_ADMIN_PASSWORD_LENGTH:
            flash(
                f"Password baru minimal {MIN_ADMIN_PASSWORD_LENGTH} karakter.",
                "error",
            )
        elif new_password != confirmation:
            flash("Konfirmasi password tidak sama.", "error")
        elif new_password == current_password:
            flash("Password baru harus berbeda dari password saat ini.", "error")
        else:
            try:
                stamp = update_password(user["id"], new_password, user["password_hash"])
            except (MySQLError, ValueError):
                flash("Password belum dapat diperbarui. Coba lagi.", "error")
            else:
                session["must_change_password"] = False
                session["credential_stamp"] = stamp
                session.pop("_csrf_token", None)
                issue_csrf_token()
                flash("Password berhasil diperbarui.", "success")
                return redirect(url_for(role_dashboard_endpoint(user["role"])))

    return render_template("auth/change_password.html")
