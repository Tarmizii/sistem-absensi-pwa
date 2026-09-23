"""Read the logged-in student's face-enrollment progress."""

from __future__ import annotations

from typing import Any

from app.database import get_db


POSE_ORDER = ("front", "left", "right")
POSE_LABELS = {"front": "Depan", "left": "Kiri", "right": "Kanan"}


class StudentEnrollmentNotFoundError(LookupError):
    """The current account is not a student with an enrollment profile."""


def get_own_enrollment_progress(user_id: int) -> dict[str, Any]:
    """Return only pose names and state for the current student account."""

    if type(user_id) is not int or user_id <= 0:
        raise StudentEnrollmentNotFoundError("Akun Siswa tidak ditemukan.")
    with get_db().cursor() as cursor:
        cursor.execute(
            """SELECT s.id AS student_id, s.face_registered, s.full_name
               FROM students AS s
               JOIN users AS u ON u.id = s.user_id
               WHERE u.id = %s AND u.role = 'student' AND u.is_active = 1
               LIMIT 1""",
            (user_id,),
        )
        student = cursor.fetchone()
        if student is None:
            raise StudentEnrollmentNotFoundError("Profil Siswa tidak ditemukan.")
        cursor.execute(
            """SELECT sf.pose FROM student_faces AS sf
               WHERE sf.student_id = %s AND sf.pose IN ('front', 'left', 'right')""",
            (student["student_id"],),
        )
        saved_poses = {row["pose"] for row in cursor.fetchall()}
    poses = [
        {"key": pose, "label": POSE_LABELS[pose], "saved": pose in saved_poses}
        for pose in POSE_ORDER
    ]
    return {
        "student_id": int(student["student_id"]),
        "full_name": student["full_name"],
        "face_registered": bool(student["face_registered"]),
        "poses": poses,
        "saved_count": sum(pose["saved"] for pose in poses),
        "total_poses": len(POSE_ORDER),
    }
