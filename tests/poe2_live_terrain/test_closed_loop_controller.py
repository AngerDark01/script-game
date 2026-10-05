import numpy as np

from auto_modules.features.poe2.live_terrain.experimental.multiplayer_follow.closed_loop_controller import (
    ClosedLoopMotionController,
)
from auto_modules.features.poe2.live_terrain.experimental.multiplayer_follow.complexity import ComplexityState
from auto_modules.features.poe2.live_terrain.experimental.multiplayer_follow.motion_models import MotionObservation, MotionPhase, MotionResponse
from auto_modules.features.poe2.live_terrain.experimental.multiplayer_follow.motion_snapshot import build_motion_snapshot


def _snapshot(position=(20.0, 20.0), target=(80.0, 20.0), clearance=20.0, age=10, confidence=0.95, role="device-a:p1"):
    walls = np.zeros((100, 100), dtype=np.uint8)
    distances = np.full((100, 100), clearance, dtype=np.float32)
    observation = MotionObservation(
        role_key=role, position=position, target=target,
        captured_at_ms=1000, frame_age_ms=age, confidence=confidence,
        map_version="map:v1", registration_version=1,
    )
    return build_motion_snapshot(
        observation=observation, wall_map=walls, distance_field=distances,
        route=(position, target), target=target, peer_position=None,
    )


def test_open_snapshot_uses_nominal_command_and_exposes_policy():
    controller = ClosedLoopMotionController()
    decision = controller.step(_snapshot(), now_ms=1000)
    assert decision.complexity.state is ComplexityState.OPEN
    assert decision.command is not None
    assert decision.command.phase is MotionPhase.ISSUE_COMMAND
    assert decision.command.stick[0] > 0.0
    assert decision.diagnostics["policy"] == "regulated_pursuit"


def test_unknown_snapshot_returns_neutral_and_stops_output():
    controller = ClosedLoopMotionController()
    decision = controller.step(_snapshot(age=900), now_ms=1000)
    assert decision.command is None
    assert decision.phase is MotionPhase.STOPPED
    assert decision.diagnostics["policy"] == "neutral"


def test_custom_runtime_frame_age_window_keeps_recovery_frame_actionable():
    controller = ClosedLoopMotionController(max_frame_age_ms=700)

    decision = controller.step(_snapshot(age=650), now_ms=1650)

    assert decision.complexity.state is ComplexityState.OPEN
    assert decision.command is not None


def test_frame_age_above_runtime_window_is_neutral():
    controller = ClosedLoopMotionController(max_frame_age_ms=700)

    decision = controller.step(_snapshot(age=701), now_ms=1701)

    assert decision.complexity.state is ComplexityState.UNKNOWN
    assert decision.command is None


def test_arrival_requires_only_local_goal_distance():
    controller = ClosedLoopMotionController(arrival_radius=4.0)
    decision = controller.step(_snapshot(position=(20.0, 20.0), target=(22.0, 20.0)), now_ms=1000)
    assert decision.command is None
    assert decision.phase is MotionPhase.ARRIVED


def test_response_updates_calibration_and_next_command_uses_same_role_state():
    controller = ClosedLoopMotionController(expected_speed=40.0)
    first = controller.step(_snapshot(), now_ms=1000)
    assert first.command is not None
    controller.record_response(
        first.command,
        MotionResponse(first.command.command_id, (4.0, 0.0), 100, 1.0, 40.0, 4.0, True, "accepted"),
        now_ms=1100,
    )
    second = controller.step(_snapshot(), now_ms=1200)
    assert second.calibration.sample_count == 1
    assert second.command is not None


def test_complexity_hysteresis_is_isolated_per_role():
    controller = ClosedLoopMotionController()
    constrained = controller.step(
        _snapshot(position=(20.0, 20.0), target=(80.0, 20.0), clearance=1.0),
        now_ms=1000,
    )
    open_role = controller.step(
        _snapshot(position=(20.0, 20.0), target=(80.0, 20.0), clearance=20.0, role="device-b:p2"),
        now_ms=1000,
    )

    assert constrained.complexity.state is ComplexityState.CONSTRAINED
    assert open_role.complexity.state is ComplexityState.OPEN
