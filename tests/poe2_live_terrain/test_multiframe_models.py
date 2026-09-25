from dataclasses import FrozenInstanceError

import numpy as np
import pytest

from auto_modules.core.localization.frame_displacement import FrameDisplacement
from auto_modules.features.poe2.live_terrain.experimental.hybrid_localization.models import (
    HybridFrame,
    PositionAnchor,
    SimilarityTransform2D,
)
from auto_modules.features.poe2.live_terrain.experimental.multiframe_localization.models import (
    CandidateRegion,
    MotionState,
    MultiFrameEvidence,
    PositionEstimate,
)


def _frame(frame_id=1, stamp=1000):
    return HybridFrame(
        frame_id=frame_id,
        captured_at_ms=stamp,
        wall_mask=np.eye(8, dtype=np.uint8),
        local_player=(4.0, 4.0),
    )


def _displacement(accepted=True, distance=2.0):
    return FrameDisplacement((distance, 0.0), 0.9, distance, accepted, "accepted")


def test_evidence_and_estimate_are_immutable_and_copy_arrays():
    evidence = MultiFrameEvidence(
        frame=_frame(),
        motion=_displacement(),
        local_offset=(0.0, 0.0),
        is_keyframe=True,
        segment_id=3,
    )
    covariance = np.eye(2, dtype=np.float64)
    region = CandidateRegion(
        transform=SimilarityTransform2D(15.0, False, 1.0, (2.0, 3.0)),
        position=(20.0, 30.0),
        covariance=covariance,
        score=0.8,
        support_frames=(1,),
    )
    estimate = PositionEstimate(
        status="confirmed",
        position=(20.0, 30.0),
        velocity=(1.0, 0.0),
        covariance=covariance,
        candidate_regions=(region,),
        instance_id="Map:A1",
        registration_version=2,
        evidence_version=4,
        fresh=True,
        age_ms=0,
        source="strategy_b",
        reason="",
    )

    covariance[:] = 0.0
    assert estimate.covariance[0, 0] == 1.0
    assert estimate.covariance.flags.writeable is False
    assert evidence.observed_mask.flags.writeable is False
    with pytest.raises(FrozenInstanceError):
        evidence.segment_id = 4


def test_models_reject_invalid_values():
    with pytest.raises(ValueError, match="segment_id"):
        MultiFrameEvidence(_frame(), _displacement(), (0.0, 0.0), True, -1)
    with pytest.raises(ValueError, match="instance_id"):
        PositionEstimate("lost", None, None, None, (), "", 0, 0, False, 0, "", "")


def test_motion_state_has_explicit_unknown_value():
    assert MotionState.STATIONARY.value == "stationary"
    assert MotionState.MOVING.value == "moving"
    assert MotionState.UNKNOWN.value == "unknown"
