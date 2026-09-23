"""Routes used by the application foundation."""

from __future__ import annotations

from flask import Blueprint, jsonify, render_template


main_bp = Blueprint("main", __name__)


@main_bp.get("/")
def index():
    """Render the foundation landing page."""

    return render_template("home.html")


@main_bp.get("/healthz")
def healthz():
    """Return a small non-sensitive readiness response."""

    return jsonify(status="ok", service="sistem-absensi-pwa")
