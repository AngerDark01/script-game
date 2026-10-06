"""Deterministic replay checks for the experimental motion composition.

These tests exercise the same runtime boundary used by the PoE2 page while
keeping the plant simulated.  They intentionally do not open a controller or
send a game input.
"""

import numpy as np

from auto_modules.features.poe2.live_terrain.experimental.multiplayer_follow import (
    ControlMode,
    FollowState,
    MapIdentity,
    PositionSample,
    RoleId,
    SimulatedFollowRuntime,
)
from auto_modules.features.poe2.live_terrain.experimental.multiplayer_follow.closed_loop_controller import (
    ClosedLoopMotionController,
)


def _sample(role, identity, point, captured_at_ms):
    return PositionSample(role, identity, point, captured_at_ms, 1.0, "simulated")


def test_replay_open_room_reaches_target_with_closed_loop():
    identity = MapIdentity("area", "replay-open")
    role = RoleId("local-device", "p1")
    runtime = SimulatedFollowRuntime(
        wall_map=np.zeros((160, 160), dtype=np.uint8),
        map_identity=identity,
        arrival_radius=2.0,
        speed_units_per_second=40.0,
        position_ttl_ms=500,
        downsample_factor=2,
        closed_loop_controller=ClosedLoopMotionController(
            expected_speed=40.0, arrival_radius=2.0,
        ),
    )
    runtime.add_follower(role, _sample(role, identity, (10.0, 80.0), 0), mode=ControlMode.SIMULATED)
    runtime.set_simulated_target((120.0, 80.0), now_ms=0)

    observation = None
    for tick in range(1, 260):
        now_ms = tick * 50
        runtime.refresh_simulated_target(now_ms=now_ms)
        observation = runtime.tick(now_ms=now_ms)[role.key]
        if observation.state is FollowState.ARRIVED:
            break

    assert observation is not None
    assert observation.state is FollowState.ARRIVED
    assert observation.diagnostics["motion_loop_policy"] in {
        "regulated_pursuit", "blended_transition", "candidate_pulse",
    }


def test_replay_wall_route_never_emits_a_colliding_route():
    identity = MapIdentity("area", "replay-door")
    walls = np.zeros((100, 100), dtype=np.uint8)
    walls[10:90, 50] = 255
    walls[47:54, 50] = 0
    role = RoleId("local-device", "p1")
    runtime = SimulatedFollowRuntime(
        wall_map=walls,
        map_identity=identity,
        arrival_radius=2.0,
        speed_units_per_second=30.0,
        downsample_factor=4,
        safety_margin=1,
        clearance_radius=8.0,
        clearance_weight=1.0,
        minimum_clearance=2.0,
        footprint_radius=2.0,
        closed_loop_controller=ClosedLoopMotionController(
            expected_speed=30.0, arrival_radius=2.0,
        ),
    )
    runtime.add_follower(role, _sample(role, identity, (20.0, 50.0), 0), mode=ControlMode.PREVIEW)
    runtime.set_simulated_target((80.0, 50.0), now_ms=0)

    observation = runtime.tick(now_ms=50)[role.key]

    assert observation.diagnostics["route_walkable"] is True
    assert observation.diagnostics["route_collision_segments"] == 0
    assert observation.diagnostics["plan_candidate_route_count"] >= 1


def test_replay_stale_visual_frame_keeps_bounded_prediction_output():
    identity = MapIdentity("area", "replay-stale")
    role = RoleId("local-device", "p1")
    runtime = SimulatedFollowRuntime(
        wall_map=np.zeros((80, 80), dtype=np.uint8),
        map_identity=identity,
        arrival_radius=2.0,
        speed_units_per_second=30.0,
        position_ttl_ms=1000,
        downsample_factor=1,
        closed_loop_controller=ClosedLoopMotionController(arrival_radius=2.0),
    )
    runtime.add_follower(role, _sample(role, identity, (10.0, 10.0), 100), mode=ControlMode.PROGRAM)
    runtime.set_simulated_target((60.0, 10.0), now_ms=100)

    observation = runtime.tick(now_ms=700)[role.key]

    assert observation.vector != (0.0, 0.0)
    assert observation.state is FollowState.PROGRAM_READY
    assert observation.diagnostics["motion_loop_state"] == "unknown"
