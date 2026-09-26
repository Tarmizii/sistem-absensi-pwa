"""Run the offline, synthetic portion of the T04 OpenCV experiment."""

from __future__ import annotations

import numpy as np
import cv2

from app.services.face_poc import (
    create_lbph_recognizer,
    predict_lbph,
    train_lbph,
)


def synthetic_sample(seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    base = np.full((200, 200), 120 + seed * 10, dtype=np.float32)
    noise = rng.normal(0, 8, size=base.shape)
    return np.clip(base + noise, 0, 255).astype(np.uint8)


def main() -> int:
    samples = [synthetic_sample(1), synthetic_sample(2), synthetic_sample(3)]
    recognizer = train_lbph(samples, [1, 1, 2])
    label, distance = predict_lbph(recognizer, samples[0])
    assert label in {1, 2}
    print(f"opencv={cv2.__version__}")
    print(f"opencv_face_module={hasattr(cv2, 'face')}")
    print(f"lbph_synthetic_prediction_label={label}")
    print(f"lbph_synthetic_distance={distance:.3f}")
    print("synthetic_poc=ok")
    print("field_android_https=not_run")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
