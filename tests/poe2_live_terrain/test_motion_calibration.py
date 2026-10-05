import numpy as np

from auto_modules.features.poe2.live_terrain.experimental.multiplayer_follow.motion_calibration import (
    AdaptiveInputCalibrator,
)
from auto_modules.features.poe2.live_terrain.experimental.multiplayer_follow.motion_models import (
    MotionCommand,
    MotionResponse,
)


def _command(role="device-a:p1", stick=(0.5, 0.0)):
    return MotionCommand(1, role, (1.0, 0.0), stick, 100, 1000, "map:v1")


def test_valid_response_updates_role_specific_calibration():
    calibrator = AdaptiveInputCalibrator(expected_speed=40.0, min_displacement=0.5)
    before = calibrator.state_for("device-a:p1")
    after = calibrator.update(
        _command(),
        MotionResponse(1, (4.0, 0.0), 100, 1.0, 40.0, 4.0, True, "accepted"),
    )
    assert after.sample_count == before.sample_count + 1
    assert after.confidence > before.confidence
    assert after.speed_gain > 0
    assert after.stick_to_native[0, 0] != before.stick_to_native[0, 0]
    assert calibrator.state_for("device-a:p2").sample_count == 0


def test_rejected_or_misaligned_response_does_not_update_model():
    calibrator = AdaptiveInputCalibrator(min_alignment=0.5)
    before = calibrator.state_for("device-a:p1")
    after = calibrator.update(
        _command(),
        MotionResponse(1, (0.0, 0.0), 100, 0.0, 0.0, 0.0, False, "stalled"),
    )
    assert after == before


def test_state_is_bounded_and_unknown_roles_do_not_share_arrays():
    calibrator = AdaptiveInputCalibrator(max_parameter_step=0.1)
    first = calibrator.state_for("a")
    second = calibrator.state_for("b")
    assert first.role_key != second.role_key
    assert not np.shares_memory(first.stick_to_native, second.stick_to_native)
