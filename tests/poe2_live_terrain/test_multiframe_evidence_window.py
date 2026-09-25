import numpy as np

from auto_modules.core.localization.frame_displacement import FrameDisplacement
from auto_modules.features.poe2.live_terrain.experimental.hybrid_localization.models import HybridFrame
from auto_modules.features.poe2.live_terrain.experimental.multiframe_localization.evidence_window import EvidenceWindow
from auto_modules.features.poe2.live_terrain.experimental.multiframe_localization.models import (
    MotionState,
    MultiFrameEvidence,
)


def _item(frame_id, segment=0, keyframe=True, distance=3.0):
    frame = HybridFrame(frame_id, frame_id * 100, np.eye(8, dtype=np.uint8), (4.0, 4.0))
    motion = FrameDisplacement((distance, 0.0), 0.9, distance, True, "accepted")
    return MultiFrameEvidence(frame, motion, (float(frame_id), 0.0), keyframe, segment)


def test_window_rejects_stationary_and_keeps_bounded_keyframes():
    window = EvidenceWindow(max_keyframes=2)
    stationary = MultiFrameEvidence(
        _item(1).frame,
        FrameDisplacement((0.0, 0.0), 0.9, 0.0, True, "accepted"),
        (0.0, 0.0),
        False,
        0,
    )
    assert not window.append(stationary)
    assert window.append(_item(2))
    assert window.append(_item(3))
    assert window.append(_item(4))
    assert tuple(item.frame.frame_id for item in window.snapshot()) == (3, 4)


def test_break_segment_clears_frames_and_increments_version():
    window = EvidenceWindow(max_keyframes=4)
    window.append(_item(1))
    old_version = window.version
    segment = window.break_segment("phase_failed")
    assert segment == 1
    assert window.version > old_version
    assert window.snapshot() == ()
    assert window.last_break_reason == "phase_failed"


def test_newer_segment_replaces_old_segment_without_rebreaking_each_frame():
    window = EvidenceWindow(max_keyframes=4)
    window.append(_item(1, segment=0))
    assert window.append(_item(2, segment=1))
    assert window.segment_id == 1
    assert window.append(_item(3, segment=1))
    assert tuple(item.frame.frame_id for item in window.snapshot()) == (2, 3)


def test_window_trims_oldest_keyframes_by_travel_distance():
    window = EvidenceWindow(max_keyframes=8, max_travel_distance=1.1)

    assert window.append(_item(1))
    assert window.append(_item(2))
    assert window.append(_item(3))

    assert tuple(item.frame.frame_id for item in window.snapshot()) == (2, 3)
    assert window.travel_distance == 1.0


def test_window_trims_oldest_keyframes_by_actual_array_bytes():
    bytes_per_item = _item(1).frame.wall_mask.nbytes + _item(1).observed_mask.nbytes
    window = EvidenceWindow(max_keyframes=8, max_bytes=bytes_per_item * 2)

    assert window.append(_item(1))
    assert window.append(_item(2))
    assert window.append(_item(3))

    assert tuple(item.frame.frame_id for item in window.snapshot()) == (2, 3)
    assert window.estimated_bytes == bytes_per_item * 2
