from __future__ import annotations

import pytest

from auto_modules.features.poe2.live_terrain.experimental.follow_engine.tracking.command_odometry import (
    CommandOdometry,
    integrate_command,
)
from auto_modules.features.poe2.live_terrain.experimental.follow_engine.tracking.position_fusion import (
    fuse_observation,
    fuse_position,
    grow_uncertainty,
    predict_position,
)
from auto_modules.features.poe2.live_terrain.experimental.follow_engine.tracking.tracking_state import RoleTrackingState
from auto_modules.features.poe2.live_terrain.experimental.follow_engine.tracking.velocity_calibrator import VelocityCalibrator


def test_command_odometry_integrates_pulse_and_grows_uncertainty():
    assert integrate_command((0, 0), (1, 0), 100, 250) == (25.0, 0.0)
    odometry = CommandOdometry((0, 0), uncertainty=2)
    estimate = odometry.step((1, 0), 100, 250, now_ms=250, speed_error_units_per_second=20, timing_error_ms=10)
    assert estimate.position == (25.0, 0.0)
    assert estimate.velocity == (100.0, 0.0)
    assert estimate.uncertainty > 2.0


def test_velocity_calibrator_uses_trusted_observation_distance():
    calibrator = VelocityCalibrator(initial_speed=80, smoothing=0.5)
    updated = calibrator.update((0, 0), (50, 0), 500, confidence=1.0)
    assert updated == 90.0
    slower = calibrator.update((50, 0), (60, 0), 500, confidence=0.0)
    assert slower == updated


def test_prediction_and_fusion_keep_visual_correction_continuous():
    predicted = predict_position((10, 20), (2, 0), (1, 0), 0.5)
    assert predicted == (10.85, 20.0)
    fused = fuse_position(predicted, (12, 20), prediction_sigma=10, observation_sigma=5)
    assert 10.85 < fused[0] < 12.0
    accepted = fuse_observation(
        predicted,
        (11.2, 20),
        prediction_sigma=10,
        observation_sigma=2,
        max_innovation=5,
    )
    assert accepted.accepted is True
    rejected = fuse_observation(
        predicted,
        (100, 20),
        prediction_sigma=10,
        observation_sigma=2,
        max_innovation=5,
    )
    assert rejected.accepted is False
    assert rejected.position == predicted


def test_uncertainty_grows_with_visual_gap_and_command_duration():
    assert grow_uncertainty(4, visual_gap_ms=500, speed_error_units_per_second=20, command_duration_ms=250, command_error_units_per_second=8) == 16.0


def test_tracking_state_reports_visual_age_and_fused_contract():
    state = RoleTrackingState("p2", (10, 20), (1, 0), 3, 900, 1000, "command_prediction")
    assert state.visual_age_ms == 100.0
    assert state.as_fused_state().source == "command_prediction"


@pytest.mark.parametrize("duration", [-1, float("nan")])
def test_odometry_rejects_invalid_duration(duration):
    with pytest.raises((TypeError, ValueError)):
        integrate_command((0, 0), (1, 0), 10, duration)
