"""Student check-in/check-out submission endpoints for T18–T19."""

from __future__ import annotations

from flask import Blueprint, abort, g, jsonify, render_template, request, send_file, url_for
from pymysql import MySQLError

from app.services.attendance_service import (
    AttendanceError,
    process_checkin_frame,
    process_checkout_frame,
    start_checkin,
    start_checkout,
)
from app.services.auth_service import roles_required
from app.services.attendance_read_service import (
    AttendanceReadError,
    get_attendance_evidence,
    get_attendance_evidence_file,
)
from app.services.storage_service import StorageError


attendance_bp = Blueprint("attendance", __name__, url_prefix="/attendance")


@attendance_bp.errorhandler(413)
def payload_too_large(_error):
    return jsonify(error="Frame terlalu besar. Coba lagi dengan kamera.", retry=True), 413


@attendance_bp.post("/checkin/start")
@roles_required("student")
def checkin_start():
    """Preflight: prove eligibility and location before the camera opens."""

    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify(error="Permintaan presensi tidak valid."), 400
    try:
        result = start_checkin(
            g.current_user["id"],
            latitude=payload.get("latitude"),
            longitude=payload.get("longitude"),
            accuracy_meters=payload.get("accuracy"),
        )
    except AttendanceError as error:
        return jsonify(error=str(error), retry=error.status_code >= 500), error.status_code
    except MySQLError:
        return jsonify(error="Layanan presensi belum tersedia. Coba lagi.", retry=True), 503
    return jsonify(result)


@attendance_bp.post("/checkin/frame")
@roles_required("student")
def checkin_frame():
    """Advance liveness and, on a verified identity, persist the check-in."""

    challenge_token = request.form.get("challenge_id", "")
    upload = request.files.get("frame")
    if upload is None:
        return jsonify(error="Frame kamera belum tersedia. Coba lagi.", retry=True), 400
    try:
        outcome = process_checkin_frame(
            g.current_user["id"], challenge_token, upload.read(), upload.mimetype
        )
    except AttendanceError as error:
        return jsonify(
            error=str(error),
            retry=error.status_code >= 500 or error.status_code == 410,
        ), error.status_code
    except StorageError:
        return jsonify(error="Gambar tidak dapat diproses. Ambil ulang.", retry=True), 422
    except (MySQLError, OSError):
        return jsonify(error="Presensi belum tersimpan. Periksa koneksi lalu coba lagi.", retry=True), 503

    body = {"captured": outcome.captured, "stage": outcome.stage,
            "message": outcome.message}
    if outcome.result is not None:
        body.update(outcome.result)
    return jsonify(body)


@attendance_bp.post("/checkout/start")
@roles_required("student")
def checkout_start():
    """Preflight for check-out: state, enrollment, and location before camera."""

    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify(error="Permintaan presensi pulang tidak valid."), 400
    try:
        result = start_checkout(
            g.current_user["id"],
            latitude=payload.get("latitude"),
            longitude=payload.get("longitude"),
            accuracy_meters=payload.get("accuracy"),
        )
    except AttendanceError as error:
        return jsonify(error=str(error), retry=error.status_code >= 500), error.status_code
    except MySQLError:
        return jsonify(error="Layanan presensi belum tersedia. Coba lagi.", retry=True), 503
    return jsonify(result)


@attendance_bp.post("/checkout/frame")
@roles_required("student")
def checkout_frame():
    """Advance check-out liveness and, on a verified identity, persist it."""

    challenge_token = request.form.get("challenge_id", "")
    upload = request.files.get("frame")
    if upload is None:
        return jsonify(error="Frame kamera belum tersedia. Coba lagi.", retry=True), 400
    try:
        outcome = process_checkout_frame(
            g.current_user["id"], challenge_token, upload.read(), upload.mimetype
        )
    except AttendanceError as error:
        return jsonify(
            error=str(error),
            retry=error.status_code >= 500 or error.status_code == 410,
        ), error.status_code
    except StorageError:
        return jsonify(error="Gambar tidak dapat diproses. Ambil ulang.", retry=True), 422
    except (MySQLError, OSError):
        return jsonify(error="Presensi pulang belum tersimpan. Periksa koneksi lalu coba lagi.", retry=True), 503

    body = {"captured": outcome.captured, "stage": outcome.stage,
            "message": outcome.message}
    if outcome.result is not None:
        body.update(outcome.result)
    return jsonify(body)


@attendance_bp.get("/<int:record_id>/evidence")
@roles_required("admin", "teacher")
def evidence_detail(record_id: int):
    try:
        model = get_attendance_evidence(user_id=g.current_user["id"],
                                        role=g.current_user["role"], record_id=record_id)
    except AttendanceReadError as error:
        abort(error.status_code, description=str(error))
    except MySQLError:
        abort(503, description="Bukti presensi belum dapat dimuat. Coba lagi.")
    if g.current_user["role"] == "teacher":
        back_url = url_for("teacher.attendance", class_id=model["class_id"],
                           month=model["date"][:7])
    else:
        back_url = url_for("admin.student_detail", student_id=model["student_id"])
    return render_template("attendance/evidence.html", model=model, back_url=back_url)


@attendance_bp.get("/<int:record_id>/evidence/<phase>/image")
@roles_required("admin", "teacher")
def evidence_image(record_id: int, phase: str):
    try:
        image_path = get_attendance_evidence_file(
            user_id=g.current_user["id"], role=g.current_user["role"],
            record_id=record_id, phase=phase,
        )
    except AttendanceReadError as error:
        abort(error.status_code, description=str(error))
    except MySQLError:
        abort(503, description="Foto bukti presensi belum dapat dimuat. Coba lagi.")
    return send_file(image_path, mimetype="image/webp", as_attachment=False,
                     download_name="bukti-presensi.webp", conditional=False,
                     max_age=0, etag=False)
