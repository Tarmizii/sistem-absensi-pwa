"""Server-side validation for manual-capture enrollment (one photo per pose)."""

from __future__ import annotations

from contextlib import contextmanager
from io import BytesIO
import tempfile
from pathlib import Path
import unittest
from unittest.mock import Mock, patch

import numpy as np
from PIL import Image
from app import create_app
from app.services.auth_service import credential_stamp
from app.services.face_enrollment_service import (
    EYES_OPEN_MESSAGE,
    FaceEnrollmentError,
    FrameAssessment,
    _inspect_frame,
    _next_stage,
    capture_enrollment_pose,
)
from app.services.face_poc import FacePocError, QualityReport
from werkzeug.security import generate_password_hash


def jpeg_frame() -> bytes:
    output = BytesIO()
    Image.new("RGB", (200, 200), (110, 110, 110)).save(output, format="JPEG")
    return output.getvalue()


def fake_crop():
    return np.zeros((90, 80, 3), dtype=np.uint8)


class FaceEnrollmentServiceTests(unittest.TestCase):
    def test_shared_blink_sequence_still_advances_open_closed_open(self):
        # Attendance check-in/out reuses this helper; enrollment no longer does.
        state = "await_open"
        transitions = []
        for eyes in (0, 2, 2, 0, 0, 1):
            next_state = _next_stage(state, eyes)
            transitions.append(next_state)
            state = next_state
        self.assertEqual(transitions, [
            "await_open", "await_closed", "await_closed",
            "await_reopen", "await_reopen", "captured",
        ])

    def test_inspection_crops_single_face_and_reports_server_eye_count(self):
        quality = QualityReport(brightness=100, sharpness=200, acceptable=True)
        with patch("app.services.face_enrollment_service.detect_single_face", return_value=(20, 30, 80, 90)), \
                patch("app.services.face_enrollment_service.assess_image_quality", return_value=quality), \
                patch("app.services.face_enrollment_service.detect_eye_count", return_value=2):
            report = _inspect_frame(jpeg_frame(), "image/jpeg")
        self.assertTrue(report.valid)
        self.assertEqual(report.eye_count, 2)
        self.assertEqual(report.face_crop.shape[:2], (90, 80))

    def test_inspection_resets_on_detector_or_quality_failure(self):
        with patch("app.services.face_enrollment_service.detect_single_face", side_effect=FacePocError("faces")):
            report = _inspect_frame(jpeg_frame(), "image/jpeg")
        self.assertFalse(report.valid)
        self.assertIn("satu wajah", report.message)

        quality = QualityReport(brightness=18, sharpness=4, acceptable=False)
        with patch("app.services.face_enrollment_service.detect_single_face", return_value=(20, 30, 80, 90)), \
                patch("app.services.face_enrollment_service.assess_image_quality", return_value=quality):
            report = _inspect_frame(jpeg_frame(), "image/jpeg")
        self.assertFalse(report.valid)
        self.assertIn("gelap", report.message)

    def test_invalid_image_is_rejected_without_face_processing(self):
        with patch("app.services.face_enrollment_service.detect_single_face") as detector:
            with self.assertRaises(FaceEnrollmentError) as caught:
                _inspect_frame(b"not an image", "image/jpeg")
        self.assertEqual(caught.exception.status_code, 422)
        detector.assert_not_called()

    def test_manual_capture_rejects_unknown_pose_before_image_processing(self):
        with patch("app.services.face_enrollment_service._inspect_frame") as inspect:
            with self.assertRaises(FaceEnrollmentError) as caught:
                capture_enrollment_pose(201, "sideways", jpeg_frame(), "image/jpeg")
        self.assertEqual(caught.exception.status_code, 400)
        inspect.assert_not_called()

    def test_manual_capture_requires_visibly_open_eyes(self):
        assessment = FrameAssessment(True, "Wajah terdeteksi.", 0, fake_crop())
        with patch("app.services.face_enrollment_service._inspect_frame", return_value=assessment):
            with self.assertRaises(FaceEnrollmentError) as caught:
                capture_enrollment_pose(201, "front", jpeg_frame(), "image/jpeg")
        self.assertEqual(caught.exception.status_code, 422)
        self.assertEqual(str(caught.exception), EYES_OPEN_MESSAGE)

    def test_manual_capture_rejects_invalid_frames(self):
        assessment = FrameAssessment(False, "Wajah terlalu gelap. Tambah cahaya.", 0, None)
        with patch("app.services.face_enrollment_service._inspect_frame", return_value=assessment):
            with self.assertRaises(FaceEnrollmentError) as caught:
                capture_enrollment_pose(201, "front", jpeg_frame(), "image/jpeg")
        self.assertEqual(caught.exception.status_code, 422)
        self.assertIn("gelap", str(caught.exception))

    def _capture_with_cursor(self, cursor, assessment):
        @contextmanager
        def fake_transaction():
            yield None, cursor

        with patch("app.services.face_enrollment_service._inspect_frame", return_value=assessment), \
                patch("app.services.face_enrollment_service.transaction", fake_transaction), \
                patch("app.services.face_enrollment_service.record_audit", return_value=1), \
                patch("app.services.face_enrollment_service._save_face_crop", return_value="faces/new.png"):
            return capture_enrollment_pose(201, "front", jpeg_frame(), "image/jpeg")

    def test_manual_capture_stores_first_pose_without_training(self):
        cursor = Mock()
        cursor.fetchone.side_effect = [
            {"id": 7, "face_registered": 0},  # _student_row
            None,  # no previous sample for this pose
        ]
        cursor.fetchall.return_value = [{"pose": "front"}]
        assessment = FrameAssessment(True, "Wajah terdeteksi.", 2, fake_crop())

        result = self._capture_with_cursor(cursor, assessment)

        self.assertTrue(result["captured"])
        self.assertEqual(result["pose"], "front")
        self.assertEqual(result["saved_poses"], ["front"])
        self.assertNotIn("enrollment_complete", result)
        inserts = [call for call in cursor.execute.call_args_list
                   if "INSERT INTO student_faces" in str(call)]
        self.assertEqual(len(inserts), 1)

    def test_manual_capture_trains_model_on_third_pose(self):
        cursor = Mock()
        cursor.fetchone.side_effect = [
            {"id": 7, "face_registered": 0},  # _student_row
            {"storage_key": "faces/old.png"},  # previous sample replaced
        ]
        cursor.fetchall.side_effect = [
            [{"pose": "front"}, {"pose": "left"}, {"pose": "right"}],  # saved poses
            [{"storage_key": "faces/a.png", "pose": "front"},
             {"storage_key": "faces/b.png", "pose": "left"},
             {"storage_key": "faces/c.png", "pose": "right"}],  # training faces
        ]
        assessment = FrameAssessment(True, "Wajah terdeteksi.", 2, fake_crop())
        recognizer = Mock()

        @contextmanager
        def fake_transaction():
            yield None, cursor

        with patch("app.services.face_enrollment_service._inspect_frame", return_value=assessment), \
                patch("app.services.face_enrollment_service.transaction", fake_transaction), \
                patch("app.services.face_enrollment_service.record_audit", return_value=1), \
                patch("app.services.face_enrollment_service._save_face_crop", return_value="faces/new.png"), \
                patch("app.services.face_enrollment_service.resolve_private_file",
                      return_value=Path("faces") / "a.png"), \
                patch("app.services.face_enrollment_service.cv2.imread", return_value=fake_crop()), \
                patch("app.services.face_enrollment_service.train_lbph", return_value=recognizer), \
                patch("app.services.face_enrollment_service.save_trained_model", return_value="models/m.yml"):
            result = capture_enrollment_pose(201, "right", jpeg_frame(), "image/jpeg")

        self.assertTrue(result["enrollment_complete"])
        self.assertEqual(result["redirect"], "/login")
        updates = [call for call in cursor.execute.call_args_list
                   if "UPDATE students SET face_registered=TRUE" in str(call)]
        self.assertEqual(len(updates), 1)


class FaceEnrollmentRouteTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.app = create_app({
            "TESTING": True,
            "SECRET_KEY": "face-route-test",
            "STORAGE_ROOT": str(Path(self.temp.name) / "private"),
        })
        self.client = self.app.test_client()
        self.user = {
            "id": 201,
            "username": "student-201",
            "password_hash": generate_password_hash("synthetic-password"),
            "role": "student",
            "is_active": 1,
            "must_change_password": 0,
            "face_registered": 0,
        }
        with self.app.app_context(), self.client.session_transaction() as session:
            session["user_id"] = self.user["id"]
            session["credential_stamp"] = credential_stamp(self.user["password_hash"])
            session["_csrf_token"] = "test-csrf-token"

    def _active_user(self, user=None):
        return patch("app.services.auth_service.fetch_active_user", return_value=user or self.user)

    def _capture_data(self, pose="front"):
        return {"pose": pose,
                "frame": (BytesIO(jpeg_frame()), "cam.jpg", "image/jpeg")}

    def test_capture_endpoint_requires_csrf_and_student_role(self):
        with self._active_user():
            missing_csrf = self.client.post("/face/enrollment/capture", data=self._capture_data())
        self.assertEqual(missing_csrf.status_code, 400)

        with self._active_user():
            with patch("app.face.routes.capture_enrollment_pose", return_value={
                "captured": True, "pose": "front", "pose_label": "Depan",
                "saved_poses": ["front"], "saved_count": 1,
                "message": "Pose depan berhasil disimpan.",
            }) as capture:
                response = self.client.post(
                    "/face/enrollment/capture", data=self._capture_data(),
                    headers={"X-CSRF-Token": "test-csrf-token"},
                )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(capture.call_args[0][:2], (201, "front"))
        self.assertEqual(response.json["saved_count"], 1)

        teacher = self.user | {"role": "teacher"}
        with self._active_user(teacher):
            denied = self.client.post(
                "/face/enrollment/capture", data=self._capture_data(),
                headers={"X-CSRF-Token": "test-csrf-token"},
            )
        self.assertEqual(denied.status_code, 403)

    def test_capture_endpoint_requires_a_camera_file(self):
        with self._active_user():
            response = self.client.post(
                "/face/enrollment/capture", data={"pose": "front"},
                headers={"X-CSRF-Token": "test-csrf-token"},
            )
        self.assertEqual(response.status_code, 400)
        self.assertIn("Frame kamera", response.json["error"])

    def test_capture_rejects_unknown_pose(self):
        with self._active_user():
            response = self.client.post(
                "/face/enrollment/capture", data=self._capture_data(pose="sideways"),
                headers={"X-CSRF-Token": "test-csrf-token"},
            )
        self.assertEqual(response.status_code, 400)

    def test_capture_reports_closed_eyes_as_retryable_guidance(self):
        with self._active_user():
            with patch("app.face.routes.capture_enrollment_pose",
                       side_effect=FaceEnrollmentError(EYES_OPEN_MESSAGE, 422)):
                response = self.client.post(
                    "/face/enrollment/capture", data=self._capture_data(),
                    headers={"X-CSRF-Token": "test-csrf-token"},
                )
        self.assertEqual(response.status_code, 422)
        self.assertIn("Mata", response.json["error"])

    def test_enrollment_complete_clears_session(self):
        with self._active_user():
            with patch("app.face.routes.capture_enrollment_pose", return_value={
                "captured": True, "pose": "right", "pose_label": "Kanan",
                "saved_poses": ["front", "left", "right"],
                "saved_count": 3, "message": "Pendaftaran wajah berhasil!",
                "enrollment_complete": True, "redirect": "/login",
            }):
                response = self.client.post(
                    "/face/enrollment/capture", data=self._capture_data(pose="right"),
                    headers={"X-CSRF-Token": "test-csrf-token"},
                )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json["enrollment_complete"])
        self.assertEqual(response.json["redirect"], "/login")
        # Session is cleared server-side; test client cookie updates on next request.
        followup = self.client.get("/student/dashboard")
        self.assertIn(followup.status_code, (302, 403))


if __name__ == "__main__":
    unittest.main()
