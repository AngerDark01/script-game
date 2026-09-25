from __future__ import annotations

import numpy as np

from auto_modules.core.localization import LocalizationResult
from auto_modules.core.localization.frame_displacement import FrameDisplacement
from auto_modules.features.poe2.live_terrain.experimental.hybrid_localization.models import (
    AbsoluteRegistration,
    HybridFrame,
    PositionAnchor,
    SimilarityTransform2D,
)
from auto_modules.features.poe2.live_terrain.experimental.multiframe_localization.models import MultiFrameEvidence
from auto_modules.features.poe2.live_terrain.experimental.multiframe_localization.registration_validator import RegistrationValidator


def _registration(position=(10.0, 10.0), *, angle=0.0):
    return AbsoluteRegistration(
        LocalizationResult(position, 0.9, source="test", registration_valid=True),
        SimilarityTransform2D(angle, False, 1.0, (5.0, 5.0)),
        0.0,
        "Map:A",
    )


def _frame(frame_id, offset, shift):
    frame = HybridFrame(frame_id, frame_id * 100, np.eye(8, dtype=np.uint8) * 255, (5.0, 5.0))
    motion = FrameDisplacement(shift, 0.9, float(np.hypot(*shift)), True, "accepted")
    return MultiFrameEvidence(frame, motion, offset, True, 0)


def test_validator_accepts_anchor_aligned_registration_and_consistent_trajectory():
    frames = (_frame(1, (0.0, 0.0), (0.0, 0.0)), _frame(2, (-2.0, 0.0), (2.0, 0.0)))

    decision = RegistrationValidator(min_support_frames=2).validate(
        _registration(),
        anchor=PositionAnchor((10.0, 10.0), "Map:A", 100, "memory"),
        frames=frames,
        support_frames=(1, 2),
        holdout_error=1.0,
        best_error=1.0,
        second_error=2.0,
    )

    assert decision.confirmed
    assert decision.reason == "confirmed"


def test_validator_rejects_registration_outside_anchor_uncertainty():
    decision = RegistrationValidator(min_support_frames=1, max_anchor_error=2.0).validate(
        _registration(position=(30.0, 30.0)),
        anchor=PositionAnchor((10.0, 10.0), "Map:A", 100, "memory"),
        frames=(_frame(1, (0.0, 0.0), (0.0, 0.0)),),
        support_frames=(1,),
        holdout_error=1.0,
        best_error=1.0,
        second_error=2.0,
    )

    assert not decision.confirmed
    assert decision.reason == "anchor_uncertainty"


def test_validator_rejects_broken_visual_trajectory():
    frames = (_frame(1, (0.0, 0.0), (0.0, 0.0)), _frame(2, (4.0, 0.0), (2.0, 0.0)))

    decision = RegistrationValidator(min_support_frames=2, max_trajectory_error=1.0).validate(
        _registration(),
        anchor=PositionAnchor((10.0, 10.0), "Map:A", 100, "memory"),
        frames=frames,
        support_frames=(1, 2),
        holdout_error=1.0,
        best_error=1.0,
        second_error=2.0,
    )

    assert not decision.confirmed
    assert decision.reason == "trajectory_error"
