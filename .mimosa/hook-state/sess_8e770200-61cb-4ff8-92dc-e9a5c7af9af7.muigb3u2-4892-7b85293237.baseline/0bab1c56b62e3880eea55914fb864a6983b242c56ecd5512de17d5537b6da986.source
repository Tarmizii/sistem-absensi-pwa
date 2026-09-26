"""Authenticated, student-owned face enrollment endpoints."""

from __future__ import annotations

from flask import Blueprint, g, jsonify, request, session
from pymysql import MySQLError

from app.services.auth_service import roles_required
from app.services.face_enrollment_service import (
    FaceEnrollmentError,
    capture_enrollment_pose,
)
from app.services.storage_service import StorageError


face_bp = Blueprint("face", __name__, url_prefix="/face")


@face_bp.errorhandler(413)
def payload_too_large(_error):
    return jsonify(error="Frame terlalu besar. Coba lagi dengan kamera.", retry=True), 413


@face_bp.post("/enrollment/capture")
@roles_required("student")
def enrollment_capture():
    pose = request.form.get("pose", "")
    upload = request.files.get("frame")
    if upload is None:
        return jsonify(error="Frame kamera belum tersedia. Coba lagi.", retry=True), 400
    try:
        result = capture_enrollment_pose(
            g.current_user["id"], pose, upload.read(), upload.mimetype
        )
    except FaceEnrollmentError as error:
        return jsonify(error=str(error), retry=error.status_code >= 500), error.status_code
    except StorageError:
        return jsonify(error="Gambar tidak dapat diproses. Ambil ulang pose.", retry=True), 422
    except (MySQLError, OSError):
        return jsonify(error="Sampel belum tersimpan. Periksa koneksi lalu coba lagi.", retry=True), 503
    if result.get("enrollment_complete"):
        session.clear()
    return jsonify(result)
