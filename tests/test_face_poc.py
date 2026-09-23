"""Offline checks for the provisional T04 OpenCV seam."""

from __future__ import annotations

import unittest
from unittest.mock import patch

import cv2
import numpy as np

from app.services.face_poc import (
    FacePocError,
    ProvisionalBlinkTracker,
    assess_image_quality,
    detect_single_face,
    predict_lbph,
    preprocess_face,
    train_lbph,
)


class FacePocTests(unittest.TestCase):
    def test_preprocess_normalizes_color_frame(self) -> None:
        frame = np.zeros((80, 100, 3), dtype=np.uint8)
        processed = preprocess_face(frame)
        self.assertEqual(processed.shape, (200, 200))
        self.assertEqual(processed.dtype, np.uint8)

    def test_quality_rejects_dark_blurry_frame(self) -> None:
        report = assess_image_quality(np.zeros((100, 100), dtype=np.uint8))
        self.assertFalse(report.acceptable)

    def test_detector_requires_exactly_one_face(self) -> None:
        class FakeCascade:
            def detectMultiScale(self, *_args, **_kwargs):
                return np.asarray([[1, 2, 30, 30], [40, 2, 30, 30]])

        with patch("app.services.face_poc._cascade", return_value=FakeCascade()):
            with self.assertRaises(FacePocError):
                detect_single_face(np.zeros((100, 100), dtype=np.uint8))

    def test_provisional_blink_requires_open_then_closed(self) -> None:
        tracker = ProvisionalBlinkTracker()
        self.assertFalse(tracker.observe(0))
        self.assertFalse(tracker.observe(2))
        self.assertTrue(tracker.observe(0))
        self.assertFalse(tracker.observe(0))

    def test_lbph_training_and_prediction_use_consistent_pipeline(self) -> None:
        rng = np.random.default_rng(42)
        samples = [rng.integers(0, 256, (200, 200), dtype=np.uint8) for _ in range(3)]
        recognizer = train_lbph(samples, [1, 1, 2])
        label, distance = predict_lbph(recognizer, samples[0])
        self.assertIn(label, {1, 2})
        self.assertIsInstance(distance, float)

    def test_contrib_face_module_is_available(self) -> None:
        self.assertTrue(hasattr(cv2, "face"))


if __name__ == "__main__":
    unittest.main()
