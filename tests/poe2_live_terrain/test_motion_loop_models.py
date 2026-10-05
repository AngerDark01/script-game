import numpy as np
import pytest

from auto_modules.features.poe2.live_terrain.experimental.multiplayer_follow.motion_models import (
    MotionCommand,
    MotionObservation,
    MotionPhase,
    MotionResponse,
    MotionCalibrationState,
)
from auto_modules.features.poe2.live_terrain.experimental.multiplayer_follow.motion_snapshot import (
    MotionSnapshot,
    build_motion_snapshot,
)


def _observation(**overrides):
    values = {
        "role_key": "device-a:p1",
        "position": (10.0, 20.0),
        "target": (80.0, 20.0),
        "captured_at_ms": 1000,
        "frame_age_ms": 10,
        "confidence": 0.9,
        "map_version": "map:v1",
        "registration_version": 1,
    }
    values.update(overrides)
    return MotionObservation(**values)


def test_motion_contracts_are_finite_and_diagnostics_are_immutable():
    observation = _observation()
    command = MotionCommand(
        command_id=3,
        role_key=observation.role_key,
        desired_native_vector=(1.0, 0.0),
        stick=(0.5, 0.0),
        duration_ms=80,
        issued_at_ms=1000,
        map_version=observation.map_version,
    )
    response = MotionResponse(
        command_id=3,
        displacement=(4.0, 0.0),
        elapsed_ms=100,
        alignment=1.0,
        speed=40.0,
        progress=4.0,
        accepted=True,
        reason="accepted",
    )
    assert observation.position == (10.0, 20.0)
    assert command.duration_ms == 80
    assert response.accepted
    with pytest.raises(TypeError):
        response.diagnostics["x"] = 1


def test_calibration_state_is_bounded_and_role_scoped():
    state = MotionCalibrationState(role_key="device-a:p1")
    assert state.role_key == "device-a:p1"
    assert state.stick_to_native.shape == (2, 2)
    assert np.allclose(state.stick_to_native, np.eye(2))
    with pytest.raises(ValueError):
        MotionCalibrationState(role_key="", speed_gain=0.0)


def test_snapshot_rejects_mixed_map_versions_and_keeps_wall_data_read_only():
    walls = np.zeros((8, 8), dtype=np.uint8)
    snapshot = build_motion_snapshot(
        observation=_observation(),
        wall_map=walls,
        distance_field=np.ones_like(walls, dtype=np.float32),
        route=((10.0, 20.0), (80.0, 20.0)),
        target=(80.0, 20.0),
        peer_position=None,
    )
    assert isinstance(snapshot, MotionSnapshot)
    assert not snapshot.wall_map.flags.writeable
    with pytest.raises(ValueError):
        snapshot.wall_map[0, 0] = 255
    with pytest.raises(ValueError):
        build_motion_snapshot(
            observation=_observation(map_version="map:v2"),
            wall_map=walls,
            distance_field=np.ones_like(walls, dtype=np.float32),
        route=(),
        target=(80.0, 20.0),
        peer_position=None,
        map_version="map:v1",
    )


def test_motion_phase_is_explicit():
    assert {item.value for item in MotionPhase} >= {
        "idle", "issue_command", "wait_feedback", "recovering", "stopped"
    }
