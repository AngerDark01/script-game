import cv2
import numpy as np

from auto_modules.core.localization.frame_displacement import (
    estimate_bounded_displacement,
)


def _pattern():
    image = np.zeros((64, 64), dtype=np.uint8)
    cv2.line(image, (8, 12), (50, 12), 255, 2)
    cv2.line(image, (50, 12), (50, 48), 255, 2)
    cv2.circle(image, (25, 35), 5, 255, -1)
    return image


def test_translated_pattern_is_accepted():
    previous = _pattern()
    current = np.roll(np.roll(previous, -3, axis=0), 4, axis=1)

    result = estimate_bounded_displacement(previous, current, min_quality=0.01)

    assert result.accepted
    assert result.shift == tuple(float(value) for value in (4.0, -3.0)) or result.distance > 1.0


def test_large_low_quality_shift_is_rejected():
    previous = _pattern()
    current = np.zeros_like(previous)

    result = estimate_bounded_displacement(previous, current, min_quality=0.99)

    assert not result.accepted
    assert result.reason in {"low_quality", "phase_failed"}
