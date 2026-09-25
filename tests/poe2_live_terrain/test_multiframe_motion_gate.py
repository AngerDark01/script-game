import cv2
import numpy as np

from auto_modules.features.poe2.live_terrain.experimental.hybrid_localization.models import HybridFrame
from auto_modules.features.poe2.live_terrain.experimental.multiframe_localization.motion_gate import (
    MotionGate,
)
from auto_modules.features.poe2.live_terrain.experimental.multiframe_localization.models import MotionState


def _frame(frame_id, image, stamp=None):
    return HybridFrame(frame_id, stamp or frame_id * 100, image, (32.0, 32.0))


def _pattern():
    image = np.zeros((64, 64), dtype=np.uint8)
    cv2.line(image, (8, 12), (50, 12), 255, 2)
    cv2.line(image, (50, 12), (50, 48), 255, 2)
    cv2.circle(image, (25, 35), 5, 255, -1)
    return image


def test_stationary_does_not_admit_keyframe():
    image = _pattern()
    decision = MotionGate(min_quality=0.01, movement_dead_zone=1.0, keyframe_distance=2.0).decide(
        _frame(1, image), _frame(2, image.copy()), elapsed_ms=100
    )
    assert decision.state is MotionState.STATIONARY
    assert not decision.should_capture_keyframe


def test_moving_admits_keyframe_after_distance_threshold():
    previous = _pattern()
    current = np.roll(np.roll(previous, -3, axis=0), 4, axis=1)
    decision = MotionGate(min_quality=0.01, movement_dead_zone=1.0, keyframe_distance=2.0).decide(
        _frame(1, previous), _frame(2, current), elapsed_ms=100
    )
    assert decision.state is MotionState.MOVING
    assert decision.should_capture_keyframe


def test_large_gap_or_low_quality_is_unknown_not_stationary():
    image = _pattern()
    decision = MotionGate(max_frame_gap_ms=50).decide(
        _frame(1, image), _frame(2, np.zeros_like(image)), elapsed_ms=100
    )
    assert decision.state is MotionState.UNKNOWN
    assert not decision.should_capture_keyframe
