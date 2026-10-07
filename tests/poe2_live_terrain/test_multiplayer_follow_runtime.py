from __future__ import annotations

import numpy as np
import pytest

from auto_modules.core.routing.geometry import line_is_walkable
from auto_modules.core.routing.local_controller import LocalMotionController
from auto_modules.features.poe2.live_terrain.experimental.multiplayer_follow import (
    ControlMode,
    FollowObservation,
    FollowState,
    MapIdentity,
    PositionSample,
    ProgramFollowOutput,
    RoleId,
    SimulatedFollowRuntime,
)
from auto_modules.features.poe2.live_terrain.experimental.multiplayer_follow.closed_loop_controller import (
    ClosedLoopMotionController,
)


def _position(role, map_identity, point, now=100):
    return PositionSample(role, map_identity, point, now, 1.0, "simulated")


def _runtime():
    map_identity = MapIdentity("area", "instance-1")
    walls = np.zeros((64, 64), dtype=np.uint8)
    return map_identity, SimulatedFollowRuntime(
        wall_map=walls,
        map_identity=map_identity,
        arrival_radius=2.0,
        speed_units_per_second=20.0,
        position_ttl_ms=200,
        downsample_factor=2,
    )


def test_live_target_preserves_real_role_and_rejects_old_capture():
    identity, runtime = _runtime()
    leader = RoleId("local-device", "p1")
    sample = PositionSample(leader, identity, (25.0, 20.0), 100, 1.0, "visual")
    assert runtime.set_target_sample(sample) == sample
    assert runtime.remote.position == sample
    older = PositionSample(leader, identity, (30.0, 20.0), 99, 1.0, "visual")
    assert runtime.set_target_sample(older) is None
    assert runtime.remote.position == sample
    with pytest.raises(ValueError, match="map identity"):
        runtime.set_target_sample(PositionSample(
            leader, MapIdentity("area", "another-instance"), (25.0, 20.0), 101, 1.0, "visual",
        ))


def test_live_follow_holds_arrival_until_resume_radius():
    identity = MapIdentity("area", "instance-1")
    leader = RoleId("local-device", "p1")
    follower = RoleId("local-device", "p2")
    runtime = SimulatedFollowRuntime(
        wall_map=np.zeros((64, 64), dtype=np.uint8), map_identity=identity,
        arrival_radius=3.0, resume_radius=8.0, position_ttl_ms=500,
        downsample_factor=2,
    )
    runtime.add_follower(follower, _position(follower, identity, (10, 10)), mode=ControlMode.PROGRAM)
    runtime.set_target_sample(PositionSample(leader, identity, (12, 10), 100, 1.0, "visual"))
    assert runtime.tick(now_ms=100)[follower.key].state is FollowState.ARRIVED
    runtime.set_target_sample(PositionSample(leader, identity, (16, 10), 110, 1.0, "visual"))
    assert runtime.tick(now_ms=110)[follower.key].state is FollowState.ARRIVED
    runtime.set_target_sample(PositionSample(leader, identity, (20, 10), 120, 1.0, "visual"))
    assert runtime.tick(now_ms=120)[follower.key].state is FollowState.PROGRAM_READY


def test_wall_estimate_does_not_count_as_observed_stall_or_contact():
    identity = MapIdentity("area", "instance-1")
    role = RoleId("local-device", "actor")
    target = RoleId("local-device", "leader")
    runtime = SimulatedFollowRuntime(
        wall_map=np.zeros((64, 64), dtype=np.uint8), map_identity=identity,
        arrival_radius=2.0, position_ttl_ms=1000, downsample_factor=2,
        stalled_ticks=2,
    )
    runtime.add_follower(
        role, PositionSample(role, identity, (10, 10), 100, 1.0, "visual"),
        mode=ControlMode.PROGRAM,
    )
    runtime.set_target_sample(PositionSample(target, identity, (40, 10), 100, 1.0, "visual"))
    runtime.tick(now_ms=100)
    for now in (150, 200, 250):
        runtime.update_follower_position(
            PositionSample(role, identity, (10, 10), now, 0.7, "wall_estimate")
        )
        result = runtime.tick(now_ms=now)[role.key]
        assert result.diagnostics["no_progress_ticks"] == 0
        assert result.diagnostics["contact_evidence"] is None
        assert result.state is FollowState.PROGRAM_READY


def test_command_prediction_does_not_count_as_feedback_or_confirm_arrival():
    identity = MapIdentity("area", "instance-1")
    role = RoleId("local-device", "actor")
    target = RoleId("local-device", "leader")
    runtime = SimulatedFollowRuntime(
        wall_map=np.zeros((64, 64), dtype=np.uint8), map_identity=identity,
        arrival_radius=2.0, position_ttl_ms=1000, downsample_factor=2,
        stalled_ticks=2,
    )
    runtime.add_follower(role, PositionSample(role, identity, (10, 10), 100, 1.0, "visual"), mode=ControlMode.PROGRAM)
    runtime.set_target_sample(PositionSample(target, identity, (40, 10), 100, 1.0, "visual"))
    runtime.tick(now_ms=100)
    for now, point in ((150, (10, 10)), (200, (20, 10)), (250, (39, 10))):
        runtime.update_follower_position(PositionSample(role, identity, point, now, 0.7, "command_prediction"))
        result = runtime.tick(now_ms=now)[role.key]
        assert result.diagnostics["no_progress_ticks"] == 0
        assert result.diagnostics["contact_evidence"] is None
    assert result.state is not FollowState.ARRIVED
    assert result.reason == "arrival_unconfirmed"


def test_hidden_target_cannot_confirm_arrival_at_last_known_position():
    identity = MapIdentity("area", "instance-1")
    role = RoleId("local-device", "actor")
    leader = RoleId("local-device", "leader")
    runtime = SimulatedFollowRuntime(
        wall_map=np.zeros((64, 64), dtype=np.uint8), map_identity=identity,
        arrival_radius=3.0, position_ttl_ms=1000, downsample_factor=2,
    )
    runtime.add_follower(role, PositionSample(role, identity, (20, 20), 100, 1.0, "visual"), mode=ControlMode.PROGRAM)
    runtime.set_target_sample(PositionSample(leader, identity, (21, 20), 101, 0.7, "target_hold"))
    result = runtime.tick(now_ms=101)[role.key]
    assert result.state is FollowState.WAITING_POSITION
    assert result.reason == "target_arrival_unconfirmed"


def test_continuous_follow_holds_near_hidden_target_without_entering_waiting():
    identity = MapIdentity("area", "instance-1")
    role = RoleId("local-device", "actor")
    leader = RoleId("local-device", "leader")
    runtime = SimulatedFollowRuntime(
        wall_map=np.zeros((64, 64), dtype=np.uint8), map_identity=identity,
        arrival_radius=3.0, resume_radius=8.0, position_ttl_ms=1000,
        downsample_factor=2, continuous_follow=True,
    )
    runtime.add_follower(
        role, PositionSample(role, identity, (20, 20), 100, 1.0, "visual"),
        mode=ControlMode.PROGRAM,
    )
    runtime.set_target_sample(
        PositionSample(leader, identity, (21, 20), 101, 0.7, "target_hold")
    )

    result = runtime.tick(now_ms=101)[role.key]

    assert result.state is FollowState.FOLLOW_HOLD
    assert result.reason == "follow_hold_target_unconfirmed"
    assert result.vector == (0.0, 0.0)


def test_continuous_follow_keeps_session_when_visual_position_is_near_target():
    identity = MapIdentity("area", "instance-1")
    role = RoleId("local-device", "actor")
    leader = RoleId("local-device", "leader")
    runtime = SimulatedFollowRuntime(
        wall_map=np.zeros((64, 64), dtype=np.uint8), map_identity=identity,
        arrival_radius=3.0, position_ttl_ms=1000, downsample_factor=2,
        continuous_follow=True,
    )
    runtime.add_follower(
        role, PositionSample(role, identity, (20, 20), 100, 1.0, "visual"),
        mode=ControlMode.PROGRAM,
    )
    runtime.set_target_sample(
        PositionSample(leader, identity, (21, 20), 101, 1.0, "visual")
    )

    result = runtime.tick(now_ms=101)[role.key]

    assert result.state is FollowState.FOLLOW_HOLD
    assert result.reason == "follow_hold_within_radius"
    assert result.vector == (0.0, 0.0)


def test_predicted_role_uses_short_reacquisition_pulse_without_false_stall():
    identity = MapIdentity("area", "instance-1")
    role = RoleId("local-device", "actor")
    leader = RoleId("local-device", "leader")
    walls = np.zeros((80, 80), dtype=np.uint8)
    walls[22:30, 22] = 255
    runtime = SimulatedFollowRuntime(
        wall_map=walls, map_identity=identity, arrival_radius=2.0,
        position_ttl_ms=1000, downsample_factor=2,
    )
    runtime.add_follower(role, PositionSample(role, identity, (15, 20), 100, 1.0, "visual"), mode=ControlMode.PROGRAM)
    runtime.set_target_sample(PositionSample(leader, identity, (55, 20), 100, 1.0, "visual"))
    runtime.update_follower_position(PositionSample(role, identity, (17, 20), 150, 0.7, "command_prediction"))
    result = runtime.tick(now_ms=150)[role.key]
    assert result.state is FollowState.PROGRAM_READY
    assert result.vector != (0.0, 0.0)
    assert result.diagnostics["command_duration_ms"] <= 80
    assert result.diagnostics["motion_loop_policy"] == "bounded_reacquisition_pulse"
    assert result.diagnostics["contact_evidence"] is None


def test_optional_closed_loop_shares_one_snapshot_and_publishes_policy_diagnostics():
    identity = MapIdentity("area", "instance-1")
    role = RoleId("local-device", "p2")
    runtime = SimulatedFollowRuntime(
        wall_map=np.zeros((100, 100), dtype=np.uint8),
        map_identity=identity,
        arrival_radius=2.0,
        speed_units_per_second=20.0,
        position_ttl_ms=200,
        downsample_factor=1,
        closed_loop_controller=ClosedLoopMotionController(arrival_radius=2.0),
    )
    runtime.add_follower(role, _position(role, identity, (10, 10)), mode=ControlMode.PREVIEW)
    runtime.set_simulated_target((80, 10), now_ms=100)
    observation = runtime.tick(now_ms=120)[role.key]
    assert observation.diagnostics["motion_loop_policy"] == "regulated_pursuit"
    assert observation.diagnostics["motion_loop_state"] == "open"


def test_closed_loop_uses_prediction_during_stale_frame_gap():
    identity = MapIdentity("area", "instance-1")
    role = RoleId("local-device", "p2")
    runtime = SimulatedFollowRuntime(
        wall_map=np.zeros((100, 100), dtype=np.uint8),
        map_identity=identity,
        arrival_radius=2.0,
        speed_units_per_second=20.0,
        position_ttl_ms=1000,
        downsample_factor=1,
        closed_loop_controller=ClosedLoopMotionController(arrival_radius=2.0),
    )
    runtime.add_follower(role, _position(role, identity, (10, 10), now=100), mode=ControlMode.PREVIEW)
    runtime.set_simulated_target((80, 10), now_ms=100)

    observation = runtime.tick(now_ms=700)[role.key]

    assert observation.vector != (0.0, 0.0)
    assert observation.state is FollowState.PREVIEWING


def test_closed_loop_command_duration_is_not_replaced_by_slow_tick_interval():
    identity = MapIdentity("area", "instance-1")
    role = RoleId("local-device", "p1")
    runtime = SimulatedFollowRuntime(
        wall_map=np.zeros((100, 100), dtype=np.uint8),
        map_identity=identity,
        arrival_radius=2.0,
        speed_units_per_second=20.0,
        position_ttl_ms=2000,
        downsample_factor=1,
        closed_loop_controller=ClosedLoopMotionController(
            expected_speed=20.0, arrival_radius=2.0,
        ),
    )
    runtime.add_follower(role, _position(role, identity, (10, 10), now=100), mode=ControlMode.PREVIEW)
    runtime.set_simulated_target((80, 10), now_ms=100)

    runtime.tick(now_ms=100)[role.key]
    runtime.update_follower_position(_position(role, identity, (10, 10), now=1000))
    observation = runtime.tick(now_ms=1000)[role.key]

    assert observation.diagnostics["command_duration_ms"] == 160


def test_route_can_escape_a_valid_character_start_that_is_close_to_wall():
    identity = MapIdentity("area", "instance-1")
    walls = np.zeros((80, 80), dtype=np.uint8)
    walls[:, 10] = 255
    role = RoleId("local-device", "p1")
    runtime = SimulatedFollowRuntime(
        wall_map=walls,
        map_identity=identity,
        arrival_radius=2.0,
        speed_units_per_second=20.0,
        downsample_factor=2,
        minimum_clearance=6.0,
        footprint_radius=2.0,
    )
    runtime.add_follower(role, _position(role, identity, (15, 40)), mode=ControlMode.PREVIEW)
    runtime.set_simulated_target((50, 40), now_ms=100)

    observation = runtime.tick(now_ms=120)[role.key]

    assert observation.state is FollowState.PREVIEWING
    assert observation.diagnostics["route_walkable"] is True


def test_closed_loop_snapshot_includes_other_role_for_peer_risk():
    identity = MapIdentity("area", "instance-1")
    p1 = RoleId("local-device", "p1")
    p2 = RoleId("local-device", "p2")
    runtime = SimulatedFollowRuntime(
        wall_map=np.zeros((100, 100), dtype=np.uint8),
        map_identity=identity,
        arrival_radius=2.0,
        speed_units_per_second=20.0,
        downsample_factor=1,
        closed_loop_controller=ClosedLoopMotionController(arrival_radius=2.0),
    )
    runtime.add_follower(p1, _position(p1, identity, (20, 20)), mode=ControlMode.PREVIEW)
    runtime.add_follower(p2, _position(p2, identity, (24, 20)), mode=ControlMode.PREVIEW)
    runtime.set_simulated_target((80, 20), now_ms=100)

    observation = runtime.tick(now_ms=120)[p1.key]

    assert observation.diagnostics["local_controller"]["peer_risk"] > 0.0


def test_clicked_point_is_a_simulated_remote_role_and_preview_does_not_move():
    identity, runtime = _runtime()
    follower = RoleId("local-device", "p2")
    runtime.add_follower(follower, _position(follower, identity, (5, 5)), mode=ControlMode.PREVIEW)
    target = runtime.set_simulated_target((50, 50), now_ms=100)

    observation = runtime.tick(now_ms=120)[follower.key]

    assert target.role == RoleId("simulated-device", "remote-leader")
    assert target.source == "simulated"
    assert observation.state is FollowState.PREVIEWING
    assert observation.diagnostics["coordinate_space"] == "reference_native"
    assert observation.diagnostics["route_points"] == len(observation.route)
    assert observation.diagnostics["route_length"] >= 0.0


def test_simulated_mode_advances_only_after_a_second_tick():
    identity, runtime = _runtime()
    follower = RoleId("local-device", "p2")
    runtime.add_follower(follower, _position(follower, identity, (5, 5)), mode=ControlMode.SIMULATED)
    runtime.set_simulated_target((50, 50), now_ms=100)

    first = runtime.tick(now_ms=100)[follower.key]
    second = runtime.tick(now_ms=150)[follower.key]

    assert first.vector != (0.0, 0.0)
    assert second.position is not None
    assert second.position != (5.0, 5.0)


def test_manual_mode_releases_route_without_touching_other_followers():
    identity, runtime = _runtime()
    p1 = RoleId("local-device", "p1")
    p2 = RoleId("local-device", "p2")
    runtime.add_follower(p1, _position(p1, identity, (5, 5)), mode=ControlMode.MANUAL)
    runtime.add_follower(p2, _position(p2, identity, (8, 8)), mode=ControlMode.PREVIEW)
    runtime.set_simulated_target((50, 50), now_ms=100)

    result = runtime.tick(now_ms=120)

    assert result[p1.key].reason == "manual_control"
    assert result[p1.key].route == ()
    assert result[p2.key].route


def test_stale_target_is_held_and_map_mismatch_still_fails_closed():
    identity, runtime = _runtime()
    follower = RoleId("local-device", "p2")
    runtime.add_follower(follower, _position(follower, identity, (5, 5), now=250), mode=ControlMode.PROGRAM)
    runtime.set_simulated_target((50, 50), now_ms=100)

    stale = runtime.tick(now_ms=301)[follower.key]
    assert stale.reason == "route_ready"
    assert stale.vector != (0.0, 0.0)

    with pytest.raises(ValueError, match="map identity"):
        runtime.update_follower_position(
            _position(follower, MapIdentity("area", "other"), (5, 5), now=302)
        )


def test_simulated_target_heartbeat_keeps_static_click_fresh():
    identity, runtime = _runtime()
    follower = RoleId("local-device", "p2")
    runtime.add_follower(follower, _position(follower, identity, (5, 5), now=250), mode=ControlMode.PREVIEW)
    runtime.set_simulated_target((50, 50), now_ms=100)

    runtime.refresh_simulated_target(now_ms=250)
    observation = runtime.tick(now_ms=301)[follower.key]

    assert observation.reason == "route_ready"
    assert observation.target_position == (50.0, 50.0)


def test_preview_runtime_enters_lateral_recovery_after_repeated_no_progress():
    identity, runtime = _runtime()
    role = RoleId("local-device", "p2")
    runtime.add_follower(role, _position(role, identity, (5, 5)), mode=ControlMode.PREVIEW)
    runtime.set_simulated_target((50, 50), now_ms=100)

    reasons = []
    for index in range(5):
        now = 100 + index * 40
        if index:
            runtime.update_follower_position(_position(role, identity, (5, 5), now=now))
        reasons.append(runtime.tick(now_ms=now)[role.key].reason)

    assert any(
        reason in {"stalled_recovery", "stalled_replanned", "stalled_no_escape"}
        for reason in reasons
    )


def test_program_runtime_uses_local_contact_evidence_before_global_timeout():
    identity, runtime = _runtime()
    role = RoleId("local-device", "p2")
    runtime.add_follower(role, _position(role, identity, (5, 5)), mode=ControlMode.PROGRAM)
    runtime.set_simulated_target((50, 50), now_ms=100)
    runtime.tick(now_ms=100)
    runtime.update_local_contact(
        role,
        wall_ahead=True,
        wall_distance=6.0,
        free_left=0.9,
        free_right=0.2,
        captured_at_ms=140,
    )

    runtime.update_follower_position(_position(role, identity, (5, 5), now=140))
    runtime.tick(now_ms=140)
    runtime.update_follower_position(_position(role, identity, (5, 5), now=180))
    observation = runtime.tick(now_ms=180)[role.key]

    assert observation.reason == "contact_recovery"
    assert observation.vector != (0.0, 0.0)
    assert observation.diagnostics["local_obstacle_ahead"] is True
    assert observation.diagnostics["contact_evidence"]["recovery_required"] is True


def test_stall_replans_real_target_before_declaring_no_escape(monkeypatch):
    """A failed local probe must not hide an otherwise valid target route."""
    identity, runtime = _runtime()
    role = RoleId("local-device", "p2")
    runtime.add_follower(role, _position(role, identity, (5, 5)), mode=ControlMode.PREVIEW)
    runtime.set_simulated_target((50, 50), now_ms=100)
    # Simulate the doorway probe being unavailable.  The target itself is on
    # open terrain, so a fresh route to it must remain usable.
    monkeypatch.setattr(runtime, "_recovery_waypoint", lambda *_args: None)
    reasons = []
    final = None
    for index in range(5):
        now = 100 + index * 40
        if index:
            runtime.update_follower_position(_position(role, identity, (5, 5), now=now))
        final = runtime.tick(now_ms=now)[role.key]
        reasons.append(final.reason)
    
    assert "stalled_replanned" in reasons
    assert final.reason != "stalled_no_escape"
    assert final.vector != (0.0, 0.0)


def test_wall_start_uses_bounded_escape_pulse_before_blocking():
    identity = MapIdentity("area", "instance-1")
    walls = np.zeros((50, 50), dtype=np.uint8)
    walls[25, 25] = 255
    role = RoleId("local-device", "p2")
    runtime = SimulatedFollowRuntime(
        wall_map=walls,
        map_identity=identity,
        arrival_radius=2.0,
        speed_units_per_second=20.0,
        downsample_factor=1,
        stalled_ticks=1,
    )
    runtime.add_follower(role, _position(role, identity, (25, 25)), mode=ControlMode.PROGRAM)
    runtime.set_simulated_target((40, 40), now_ms=100)

    runtime.tick(now_ms=100)
    runtime.update_follower_position(_position(role, identity, (25, 25), now=200))
    observation = runtime.tick(now_ms=200)[role.key]

    assert observation.reason == "wall_start_recovery"
    assert observation.state is FollowState.PROGRAM_READY
    assert observation.vector != (0.0, 0.0)
    assert observation.diagnostics["recovery_candidates_checked"] >= 1
    assert observation.diagnostics["plan_target_metrics"]["in_bounds"] is True


def test_wall_edge_position_recovers_on_first_plan_attempt():
    """A native position on a wall/open-space boundary must not stop early.

    Native player coordinates are continuous while the terrain layer is
    rasterized.  Rounding the coordinate can therefore select the wall cell
    even when the actor is standing immediately beside it.  The first plan
    must use the bounded local escape path instead of reporting no_safe_route.
    """
    identity = MapIdentity("area", "instance-1")
    walls = np.zeros((48, 48), dtype=np.uint8)
    walls[20, 4:44] = 255
    role = RoleId("local-device", "p2")
    runtime = SimulatedFollowRuntime(
        wall_map=walls,
        map_identity=identity,
        arrival_radius=2.0,
        speed_units_per_second=20.0,
        downsample_factor=1,
        stalled_ticks=3,
        inflate_collision=False,
    )
    # This coordinate is on the wall-side raster cell, with open terrain
    # immediately below it, matching the captured PoE2 boundary case.
    current = (12.25, 20.10)
    target = (30.0, 32.0)
    runtime.add_follower(role, _position(role, identity, current), mode=ControlMode.PROGRAM)
    runtime.set_simulated_target(target, now_ms=100)

    observation = runtime.tick(now_ms=100)[role.key]

    assert observation.reason == "wall_start_recovery"
    assert observation.vector != (0.0, 0.0)
    assert observation.reason != "no_safe_route"
    assert observation.diagnostics["recovery_candidates_checked"] >= 1

    # Until a newer visual sample leaves the raster cell, the pulse remains
    # available instead of dropping to a zero vector on the next UI tick.
    runtime.update_follower_position(_position(role, identity, current, now=150))
    repeated = runtime.tick(now_ms=150)[role.key]
    assert repeated.reason == "wall_start_recovery"
    assert repeated.vector != (0.0, 0.0)
    assert repeated.diagnostics["planning_route_walkable"] is True
    assert repeated.diagnostics["observed_position_metrics"]["collision"] == 255


def test_failed_route_cooldown_keeps_motion_alive_with_probe():
    identity = MapIdentity("area", "instance-1")
    walls = np.full((32, 32), 255, dtype=np.uint8)
    role = RoleId("local-device", "p2")
    runtime = SimulatedFollowRuntime(
        wall_map=walls,
        map_identity=identity,
        arrival_radius=2.0,
        speed_units_per_second=20.0,
        downsample_factor=1,
        inflate_collision=False,
    )
    current = (5.0, 5.0)
    runtime.add_follower(role, _position(role, identity, current), mode=ControlMode.PROGRAM)
    runtime.set_simulated_target((24.0, 24.0), now_ms=100)

    first = runtime.tick(now_ms=100)[role.key]
    assert first.reason == "no_safe_route_probe"
    assert first.vector != (0.0, 0.0)

    # The failed-plan cooldown must not convert the next control tick into a
    # terminal BLOCKED/zero-output state.  A bounded exploratory pulse keeps
    # the actor moving until a newer observation makes replanning possible.
    second = runtime.tick(now_ms=150)[role.key]
    assert second.reason == "no_safe_route_probe"
    assert second.state is FollowState.PROGRAM_READY
    assert second.vector != (0.0, 0.0)
    assert second.diagnostics["local_controller"]["policy"] == "bounded_cooldown_probe"


def test_local_contact_recovery_preempts_repeated_wall_start_pulse():
    """A confirmed minimap contact must leave the cached wall-start pulse.

    This mirrors the real wall-corner failure: the native sample remains on a
    raster wall cell, while the minimap reports free space on one side.  Once
    two command/position samples establish no progress, the runtime must use
    the lateral contact recovery path instead of returning the same tiny
    ``wall_start_recovery`` vector forever.
    """
    identity = MapIdentity("area", "instance-1")
    walls = np.zeros((48, 48), dtype=np.uint8)
    walls[20, 4:44] = 255
    role = RoleId("local-device", "p2")
    runtime = SimulatedFollowRuntime(
        wall_map=walls,
        map_identity=identity,
        arrival_radius=2.0,
        speed_units_per_second=20.0,
        downsample_factor=1,
        stalled_ticks=3,
        inflate_collision=False,
    )
    current = (12.25, 20.10)
    runtime.add_follower(role, _position(role, identity, current), mode=ControlMode.PROGRAM)
    runtime.set_simulated_target((30.0, 32.0), now_ms=100)

    first = runtime.tick(now_ms=100)[role.key]
    assert first.reason == "wall_start_recovery"

    runtime.update_local_contact(
        role,
        wall_ahead=True,
        wall_distance=6.0,
        free_left=1.0,
        free_right=0.1,
        captured_at_ms=140,
    )
    runtime.update_follower_position(_position(role, identity, current, now=140))
    runtime.tick(now_ms=140)
    runtime.update_follower_position(_position(role, identity, current, now=180))
    recovered = runtime.tick(now_ms=180)[role.key]

    assert recovered.reason == "contact_recovery"
    assert recovered.vector != (0.0, 0.0)

    # A delayed command may produce a large displacement along the previous
    # direction while the latest recovery vector points sideways.  That is
    # still movement, so it must not be escalated to relocalization merely
    # because the measured alignment is low.
    moved = (current[0] + 0.5, current[1] - 8.8)
    runtime.update_follower_position(_position(role, identity, moved, now=340))
    continued = runtime.tick(now_ms=340)[role.key]
    assert continued.reason != "contact_relocalization_required"
    assert continued.diagnostics["observed_displacement"] > 8.0


def test_open_minimap_clears_wall_start_pulse_and_reaches_progress_recovery():
    """An open live centreline must not be trapped by a stale wall raster cell."""
    identity = MapIdentity("area", "instance-1")
    walls = np.zeros((48, 48), dtype=np.uint8)
    walls[20, 4:44] = 255
    role = RoleId("local-device", "p2")
    runtime = SimulatedFollowRuntime(
        wall_map=walls,
        map_identity=identity,
        arrival_radius=2.0,
        speed_units_per_second=20.0,
        downsample_factor=1,
        stalled_ticks=1,
        inflate_collision=False,
    )
    current = (12.25, 20.10)
    runtime.add_follower(role, _position(role, identity, current), mode=ControlMode.PROGRAM)
    runtime.set_simulated_target((30.0, 32.0), now_ms=100)

    first = runtime.tick(now_ms=100)[role.key]
    assert first.reason == "wall_start_recovery"

    # The native raster still rounds onto the wall row, but the live minimap
    # says the actor is no longer blocked.  The cached wall pulse must not
    # override the normal no-progress recovery path.
    runtime.update_local_contact(
        role,
        wall_ahead=True,
        blocking_wall_ahead=False,
        escape_available=True,
        captured_at_ms=140,
    )
    runtime.update_follower_position(_position(role, identity, current, now=140))
    recovered = runtime.tick(now_ms=140)[role.key]

    assert recovered.reason == "stale_wall_raster_recovery"
    assert recovered.vector != (0.0, 0.0)
    assert recovered.diagnostics["local_obstacle_ahead"] is False


def test_wall_start_recovery_is_bounded_when_position_never_changes():
    identity = MapIdentity("area", "instance-1")
    walls = np.zeros((40, 40), dtype=np.uint8)
    walls[20, 20] = 255
    role = RoleId("local-device", "p2")
    runtime = SimulatedFollowRuntime(
        wall_map=walls,
        map_identity=identity,
        arrival_radius=2.0,
        speed_units_per_second=20.0,
        downsample_factor=1,
        stalled_ticks=1,
    )
    current = (20.0, 20.0)
    runtime.add_follower(role, _position(role, identity, current), mode=ControlMode.PROGRAM)
    runtime.set_simulated_target((32.0, 32.0), now_ms=100)

    reasons = []
    for now in (100, 150, 200, 250):
        runtime.update_follower_position(_position(role, identity, current, now=now))
        reasons.append(runtime.tick(now_ms=now)[role.key].reason)

    assert reasons[:3] == ["wall_start_recovery"] * 3
    assert reasons[3] != "wall_start_recovery"


def test_raw_side_wall_does_not_trigger_contact_recovery_when_centerline_is_open():
    identity, runtime = _runtime()
    role = RoleId("local-device", "p2")
    runtime.add_follower(role, _position(role, identity, (5, 5)), mode=ControlMode.PROGRAM)
    runtime.set_simulated_target((50, 50), now_ms=100)
    runtime.tick(now_ms=100)

    runtime.update_local_contact(
        role,
        wall_ahead=True,
        blocking_wall_ahead=False,
        escape_available=True,
        wall_distance=6.0,
        free_left=0.9,
        free_right=0.9,
        captured_at_ms=140,
    )
    runtime.update_follower_position(_position(role, identity, (5, 5), now=140))
    runtime.update_follower_position(_position(role, identity, (5.0, 6.5), now=180))
    observation = runtime.tick(now_ms=180)[role.key]

    assert observation.reason != "contact_relocalization_required"
    assert observation.diagnostics["local_raw_obstacle_ahead"] is True
    assert observation.diagnostics["local_obstacle_ahead"] is False


def test_contact_state_is_cleared_after_passing_obstacle():
    identity, runtime = _runtime()
    role = RoleId("local-device", "p2")
    runtime.add_follower(role, _position(role, identity, (5, 5)), mode=ControlMode.PROGRAM)
    runtime.set_simulated_target((50, 50), now_ms=100)
    runtime.tick(now_ms=100)
    runtime.update_local_contact(
        role,
        wall_ahead=True,
        blocking_wall_ahead=True,
        captured_at_ms=140,
    )
    runtime.update_follower_position(_position(role, identity, (5, 5), now=140))
    runtime.tick(now_ms=140)
    runtime.update_follower_position(_position(role, identity, (5, 5), now=180))
    runtime.tick(now_ms=180)

    runtime.update_local_contact(
        role,
        wall_ahead=False,
        blocking_wall_ahead=False,
        escape_available=True,
        captured_at_ms=220,
    )
    runtime.update_follower_position(_position(role, identity, (8, 5), now=220))
    escaped = runtime.tick(now_ms=220)[role.key]

    assert escaped.reason != "contact_relocalization_required"
    assert escaped.diagnostics["contact_evidence"]["consecutive_no_progress"] == 0
    assert escaped.diagnostics["contact_evidence"]["state"] == "escaped"


def test_open_local_sample_cannot_reuse_previous_contact_recovery():
    identity, runtime = _runtime()
    role = RoleId("local-device", "p2")
    runtime.add_follower(role, _position(role, identity, (5, 5)), mode=ControlMode.PROGRAM)
    runtime.set_simulated_target((50, 50), now_ms=100)
    runtime.tick(now_ms=100)
    runtime.update_local_contact(
        role,
        wall_ahead=True,
        blocking_wall_ahead=True,
        captured_at_ms=140,
    )
    runtime.update_follower_position(_position(role, identity, (5, 5), now=140))
    runtime.tick(now_ms=140)
    runtime.update_follower_position(_position(role, identity, (5, 5), now=180))
    runtime.tick(now_ms=180)

    runtime.update_local_contact(
        role,
        wall_ahead=True,
        blocking_wall_ahead=False,
        escape_available=True,
        captured_at_ms=200,
    )
    observation = runtime.tick(now_ms=200)[role.key]

    assert observation.reason != "contact_relocalization_required"


def test_blocking_contact_with_escape_keeps_searching_instead_of_relocalizing():
    identity, runtime = _runtime()
    role = RoleId("local-device", "p2")
    runtime.add_follower(role, _position(role, identity, (5, 5)), mode=ControlMode.PROGRAM)
    runtime.set_simulated_target((50, 50), now_ms=100)
    runtime.tick(now_ms=100)
    runtime.update_local_contact(
        role,
        wall_ahead=True,
        blocking_wall_ahead=True,
        escape_available=True,
        free_left=0.9,
        free_right=0.2,
        captured_at_ms=140,
    )

    reasons = []
    for now in (140, 180, 220, 260, 300):
        runtime.update_follower_position(_position(role, identity, (5, 5), now=now))
        reasons.append(runtime.tick(now_ms=now)[role.key].reason)

    assert "contact_relocalization_required" not in reasons


def test_route_is_rejected_when_coarse_path_cuts_through_wall():
    identity = MapIdentity("area", "instance-1")
    walls = np.zeros((32, 32), dtype=np.uint8)
    walls[15, :] = 255
    runtime = SimulatedFollowRuntime(
        wall_map=walls,
        map_identity=identity,
        arrival_radius=1.0,
        speed_units_per_second=20.0,
        downsample_factor=8,
    )
    follower = RoleId("local-device", "p2")
    runtime.add_follower(follower, _position(follower, identity, (10, 10)), mode=ControlMode.PREVIEW)
    runtime.set_simulated_target((10, 22), now_ms=100)

    observation = runtime.tick(now_ms=120)[follower.key]

    assert observation.state is FollowState.PREVIEWING
    assert observation.reason == "no_safe_route_probe"
    assert observation.vector != (0.0, 0.0)


def test_route_uses_real_wall_values_and_passes_through_opening():
    identity = MapIdentity("area", "instance-1")
    walls = np.zeros((64, 64), dtype=np.uint8)
    walls[4:60, 30] = 255
    walls[28:36, 30] = 0
    runtime = SimulatedFollowRuntime(
        wall_map=walls, map_identity=identity, arrival_radius=1.0,
        speed_units_per_second=20.0, downsample_factor=8,
    )
    follower = RoleId("local-device", "p1")
    runtime.add_follower(follower, _position(follower, identity, (12, 45)), mode=ControlMode.PREVIEW)
    runtime.set_simulated_target((48, 45), now_ms=100)

    observation = runtime.tick(now_ms=120)[follower.key]

    assert observation.state is FollowState.PREVIEWING
    assert observation.route
    assert observation.diagnostics["route_walkable"] is True
    assert observation.diagnostics["route_collision_segments"] == 0
    assert observation.diagnostics["plan_attempted_factors"]
    assert observation.diagnostics["plan_accepted_factor"] in observation.diagnostics["plan_attempted_factors"]
    assert all(
        line_is_walkable(runtime.wall_map, first, second, corner_safe=True)
        for first, second in zip(observation.route, observation.route[1:])
    )
    assert min(point[1] for point in observation.route) <= 35


def test_route_rejects_unsafe_first_segment_before_a_safe_waypoint(monkeypatch):
    identity = MapIdentity("area", "instance-1")
    walls = np.zeros((32, 32), dtype=np.uint8)
    walls[8:13, 10] = 255
    runtime = SimulatedFollowRuntime(wall_map=walls, map_identity=identity)
    monkeypatch.setattr(
        runtime, "_pathfinders",
        (type("FakeFinder", (), {"find_path": lambda _self, _walls, _start, _end: [(16, 10), (20, 10)]})(),),
    )

    assert runtime._plan_safe_route((4, 10), (20, 10)) is None


def test_route_inflates_walls_by_actor_footprint_before_planning():
    identity = MapIdentity("area", "instance-1")
    walls = np.zeros((100, 100), dtype=np.uint8)
    walls[:, 50] = 255
    walls[48:53, 50] = 0  # five-pixel doorway for the centre point only
    role = RoleId("local-device", "p1")

    centre_line_runtime = SimulatedFollowRuntime(
        wall_map=walls,
        map_identity=identity,
        arrival_radius=1.0,
        downsample_factor=1,
        footprint_radius=0.0,
    )
    centre_line_runtime.add_follower(
        role, _position(role, identity, (20, 50)), mode=ControlMode.PREVIEW,
    )
    centre_line_runtime.set_simulated_target((80, 50), now_ms=100)
    assert centre_line_runtime.tick(now_ms=120)[role.key].route

    body_runtime = SimulatedFollowRuntime(
        wall_map=walls,
        map_identity=identity,
        arrival_radius=1.0,
        downsample_factor=1,
        footprint_radius=3.0,
    )
    body_runtime.add_follower(
        role, _position(role, identity, (20, 50)), mode=ControlMode.PREVIEW,
    )
    body_runtime.set_simulated_target((80, 50), now_ms=100)
    blocked = body_runtime.tick(now_ms=120)[role.key]

    assert blocked.state is FollowState.PREVIEWING
    assert blocked.reason == "no_safe_route_probe"
    assert blocked.vector != (0.0, 0.0)
    assert blocked.diagnostics["route_footprint_radius"] == 3.0


def test_centerline_collision_mode_keeps_narrow_passage_open():
    identity = MapIdentity("area", "instance-1")
    walls = np.zeros((100, 100), dtype=np.uint8)
    walls[:, 50] = 255
    walls[48:53, 50] = 0  # narrow passage for the centre point
    role = RoleId("local-device", "p1")
    runtime = SimulatedFollowRuntime(
        wall_map=walls,
        map_identity=identity,
        arrival_radius=1.0,
        downsample_factor=1,
        safety_margin=0,
        minimum_clearance=0.0,
        footprint_radius=2.0,
        inflate_collision=False,
    )
    runtime.add_follower(role, _position(role, identity, (20, 50)), mode=ControlMode.PREVIEW)
    runtime.set_simulated_target((80, 50), now_ms=100)

    observation = runtime.tick(now_ms=120)[role.key]

    assert np.array_equal(runtime.collision_map, runtime.wall_map)
    assert observation.route
    assert observation.diagnostics["route_collision_inflation"] is False


def test_route_rejects_walkable_segment_that_scrapes_a_wall(monkeypatch):
    identity = MapIdentity("area", "instance-1")
    walls = np.zeros((32, 32), dtype=np.uint8)
    walls[1, :] = 255
    runtime = SimulatedFollowRuntime(
        wall_map=walls,
        map_identity=identity,
        downsample_factor=1,
        minimum_clearance=6.0,
    )
    monkeypatch.setattr(
        runtime,
        "_pathfinders",
        (type("FakeFinder", (), {"find_path": lambda _self, _walls, _start, _end: [(10, 5), (20, 5)]})(),),
    )
    assert runtime._plan_safe_route((4, 5), (24, 5)) is None


def test_explicit_actor_footprint_can_use_physically_safe_clearance_fallback(monkeypatch):
    identity = MapIdentity("area", "instance-1")
    walls = np.zeros((32, 32), dtype=np.uint8)
    walls[2, :] = 255
    runtime = SimulatedFollowRuntime(
        wall_map=walls,
        map_identity=identity,
        downsample_factor=1,
        minimum_clearance=6.0,
        footprint_radius=2.0,
    )
    monkeypatch.setattr(
        runtime,
        "_pathfinders",
        (type("FakeFinder", (), {"find_path": lambda _self, _walls, _start, _end: [(10, 5), (24, 5)]})(),),
    )

    route = runtime._plan_safe_route((4, 5), (24, 5))

    assert route
    assert runtime._last_plan_diagnostics["candidate_route_count"] == 0
    assert runtime._last_plan_diagnostics["relaxed_candidate_route_count"] == 1
    assert runtime._last_plan_diagnostics["selected_clearance_mode"] == "relaxed_clearance"


def test_route_score_prefers_open_detour_over_equally_short_wall_hug(monkeypatch):
    identity = MapIdentity("area", "instance-1")
    walls = np.zeros((45, 45), dtype=np.uint8)
    walls[10, 10:35] = 255
    runtime = SimulatedFollowRuntime(
        wall_map=walls, map_identity=identity, downsample_factor=1,
        clearance_radius=16.0, clearance_weight=4.0,
    )

    class _NearWall:
        downsample_factor = 1
        clearance_radius = 16.0
        clearance_weight = 4.0
        safety_margin = 0
        dead_end_weight = 0.0
        def find_path(self, _walls, _start, _end):
            return [(10, 6), (34, 6)]

    class _OpenDetour(_NearWall):
        downsample_factor = 2
        def find_path(self, _walls, _start, _end):
            return [(10, 34), (34, 34)]

    monkeypatch.setattr(runtime, "_pathfinders", (_NearWall(), _OpenDetour()))
    route = runtime._plan_safe_route((2, 20), (42, 20))
    assert route == [(10, 34), (34, 34)]
    assert runtime._last_plan_diagnostics["selected_route_mean_clearance"] > 10.0


def test_local_controller_chooses_lateral_candidate_before_a_wall():
    walls = np.zeros((80, 80), dtype=np.uint8)
    walls[25:41, 32] = 255
    controller = LocalMotionController(lookahead=30.0, expected_speed=80.0)
    decision = controller.command(
        (10.0, 32.0),
        (60.0, 32.0),
        ((10.0, 32.0), (60.0, 32.0)),
        desired_vector=(1.0, 0.0),
        walls=walls,
    )

    assert decision.vector != (0.0, 0.0)
    assert abs(decision.vector[1]) > 0.1
    assert decision.rejected_collision_count > 0
    assert line_is_walkable(
        walls,
        (10.0, 32.0),
        decision.predicted_position,
        corner_safe=True,
    )


def test_local_controller_reduces_magnitude_when_observed_speed_is_high():
    walls = np.zeros((80, 80), dtype=np.uint8)
    controller = LocalMotionController(expected_speed=40.0)
    slow = controller.command(
        (10.0, 10.0), (70.0, 10.0), ((10.0, 10.0), (70.0, 10.0)),
        desired_vector=(1.0, 0.0), walls=walls, observed_velocity=(0.0, 0.0),
    )
    fast = controller.command(
        (10.0, 10.0), (70.0, 10.0), ((10.0, 10.0), (70.0, 10.0)),
        desired_vector=(1.0, 0.0), walls=walls, observed_velocity=(80.0, 0.0),
    )

    assert np.linalg.norm(fast.vector) < np.linalg.norm(slow.vector)
    assert fast.diagnostics["speed_ratio"] == pytest.approx(2.0)


def test_local_controller_follows_route_that_initially_moves_away_from_goal():
    walls = np.zeros((100, 100), dtype=np.uint8)
    walls[20:80, 50] = 255
    controller = LocalMotionController(lookahead=12, expected_speed=20)
    decision = controller.command(
        (30, 60), (70, 60), ((30, 60), (30, 90), (70, 90), (70, 60)),
        desired_vector=(0, 1), walls=walls,
    )
    assert abs(decision.vector[0]) < 0.3
    assert decision.vector[1] > 0.8


def test_reused_visual_sample_does_not_count_as_multiple_stalls():
    identity, runtime = _runtime()
    role = RoleId("local-device", "p2")
    runtime.add_follower(role, _position(role, identity, (5, 5)), mode=ControlMode.PROGRAM)
    runtime.set_simulated_target((50, 50), now_ms=100)
    for now in range(100, 181, 10):
        observation = runtime.tick(now_ms=now)[role.key]
    assert observation.diagnostics["recovery_attempts"] == 0
    assert observation.diagnostics["no_progress_ticks"] == 0


def test_command_observed_direction_mismatch_triggers_lateral_recovery():
    identity, runtime = _runtime()
    role = RoleId("local-device", "p2")
    runtime.add_follower(role, _position(role, identity, (5, 5)), mode=ControlMode.PROGRAM)
    runtime.set_simulated_target((50, 5), now_ms=100)
    # First tick establishes the command.  Feed three newer visual samples
    # that move almost perpendicular to that command, as a wrong gamepad basis
    # or a wall slide would produce.
    runtime.tick(now_ms=100)
    for index, point in enumerate(((5, 8), (5, 11), (5, 14)), start=1):
        stamp = 100 + index * 100
        runtime.refresh_simulated_target(now_ms=stamp)
        runtime.update_follower_position(_position(role, identity, point, now=stamp))
        observation = runtime.tick(now_ms=stamp)
    item = observation[role.key]
    assert item.reason in {
        "direction_mismatch_recovery",
        "stalled_replanned",
        "stalled_recovery",
        "stalled_no_escape",
    }
    assert item.diagnostics["command_observed_alignment"] is not None
    assert item.diagnostics["command_observed_angle_degrees"] >= 70.0


@pytest.mark.parametrize("scenario", ["straight", "near", "door", "around_wall"])
@pytest.mark.parametrize("dt_ms", [33, 100])
def test_closed_loop_reaches_goal_without_collision_or_false_stall(scenario, dt_ms):
    identity = MapIdentity("area", "simulation")
    role = RoleId("local-device", "p1")
    walls = np.zeros((120, 120), dtype=np.uint8)
    start, target = (20, 60), (100, 60)
    if scenario == "near":
        start = (97, 60)
    elif scenario == "door":
        walls[:, 60] = 255
        walls[48:73, 60] = 0
    elif scenario == "around_wall":
        walls[20:81, 60] = 255
    runtime = SimulatedFollowRuntime(
        wall_map=walls, map_identity=identity, arrival_radius=2,
        speed_units_per_second=40, downsample_factor=2,
        footprint_radius=2, clearance_radius=12, clearance_weight=2,
        stalled_ticks=8, local_lookahead=12, prediction_horizon=0.25,
    )
    # Use PROGRAM mode with an external deterministic plant: verifies the
    # actual command/observation feedback, with no simulation-only goal snap.
    runtime.add_follower(role, _position(role, identity, start), mode=ControlMode.PROGRAM)
    runtime.set_simulated_target(target, now_ms=100)
    point = np.asarray(start, dtype=float)
    for index in range(1200):
        now = 100 + index * dt_ms
        runtime.refresh_simulated_target(now_ms=now)
        runtime.update_follower_position(_position(role, identity, point, now=now))
        observation = runtime.tick(now_ms=now)[role.key]
        if observation.state is FollowState.ARRIVED:
            break
        following = point + np.asarray(observation.vector) * 40 * dt_ms / 1000
        assert line_is_walkable(runtime.collision_map, point, following, corner_safe=True)
        point = following
    assert observation.state is FollowState.ARRIVED, (scenario, point, dict(observation.diagnostics))
    assert observation.diagnostics["recovery_attempts"] == 0


def test_program_output_is_explicitly_armed_and_released_on_manual_state():
    _identity, _runtime_instance = _runtime()
    role = RoleId("local-device", "p2")

    class FakeOutput:
        def __init__(self):
            self.calls = []

        def start(self):
            self.calls.append(("start",))

        def write(self, vector, *, elapsed_ms):
            self.calls.append(("write", vector, elapsed_ms))

        def stop(self):
            self.calls.append(("stop",))

    output = FakeOutput()
    adapter = ProgramFollowOutput({role: output})
    observation = FollowObservation(
        FollowState.PROGRAM_READY, role, RoleId("simulated-device", "remote-leader"),
        position=(5, 5), target_position=(20, 20), route=((5, 5), (20, 20)),
        vector=(1.0, 0.0),
    )

    adapter.apply(observation)
    assert output.calls == []
    adapter.arm(role)
    adapter.apply(observation, elapsed_ms=30)
    assert output.calls[-1] == ("write", (1.0, 0.0), 30)
    adapter.apply(observation.__class__(FollowState.MANUAL, role, observation.target), elapsed_ms=30)
    assert output.calls[-2][0] == "write"
    assert output.calls[-1] == ("stop",)


def test_continuous_program_output_keeps_lease_for_follow_hold():
    role = RoleId("local-device", "actor")
    target = RoleId("local-device", "leader")

    class _Output:
        def __init__(self):
            self.calls = []

        def start(self):
            self.calls.append(("start",))

        def write(self, vector, *, elapsed_ms):
            self.calls.append(("write", vector, elapsed_ms))

        def stop(self):
            self.calls.append(("stop",))

    output = _Output()
    adapter = ProgramFollowOutput({role: output}, continuous_roles={role})
    adapter.arm(role)
    observation = FollowObservation(
        FollowState.FOLLOW_HOLD,
        role,
        target,
        position=(20.0, 20.0),
        target_position=(21.0, 20.0),
        reason="follow_hold_within_radius",
    )

    adapter.apply(observation)

    assert output.calls == [("start",), ("write", (0.0, 0.0), 20)]
    assert adapter.is_armed(role)
    adapter.release_all()
    assert output.calls[-1] == ("write", (0.0, 0.0), 20)
    assert adapter.is_armed(role)
    adapter.apply(FollowObservation(
        FollowState.BLOCKED,
        role,
        target,
        position=(20.0, 20.0),
        target_position=(21.0, 20.0),
        reason="no_safe_route",
    ))
    assert adapter.is_armed(role)
    adapter.close_all()
    assert output.calls[-1] == ("stop",)
    assert not adapter.is_armed(role)


def test_continuous_follow_rearms_expired_session_on_neutral_hold_frame():
    role = RoleId("local-device", "actor")
    target = RoleId("local-device", "leader")

    class _Output:
        def __init__(self):
            self.calls = []
            self.expire_next_write = True

        def start(self):
            self.calls.append(("start",))

        def rearm(self):
            self.calls.append(("rearm",))
            self.expire_next_write = False

        def write(self, vector, *, elapsed_ms):
            if self.expire_next_write:
                self.expire_next_write = False
                raise RuntimeError("Program session expired or was revoked")
            self.calls.append(("write", vector, elapsed_ms))

        def stop(self):
            self.calls.append(("stop",))

    output = _Output()
    adapter = ProgramFollowOutput({role: output}, continuous_roles={role})
    adapter.arm(role)
    adapter.apply(FollowObservation(
        FollowState.FOLLOW_HOLD,
        role,
        target,
        position=(20.0, 20.0),
        target_position=(21.0, 20.0),
    ))

    assert output.calls == [
        ("start",),
        ("rearm",),
        ("write", (0.0, 0.0), 20),
    ]
    assert adapter.is_armed(role)


def test_program_output_uses_closed_loop_command_duration_when_present():
    _identity, _runtime_instance = _runtime()
    role = RoleId("local-device", "p2")

    class FakeOutput:
        def __init__(self):
            self.calls = []
        def start(self): pass
        def write(self, vector, *, elapsed_ms): self.calls.append((vector, elapsed_ms))
        def stop(self): pass

    output = FakeOutput()
    adapter = ProgramFollowOutput({role: output})
    adapter.arm(role)
    adapter.apply(FollowObservation(
        FollowState.PROGRAM_READY, role,
        RoleId("simulated-device", "remote-leader"),
        vector=(0.5, 0.0), diagnostics={"command_duration_ms": 160},
    ), elapsed_ms=50)

    assert output.calls == [((0.5, 0.0), 160)]


def test_program_output_rearms_once_when_host_session_expires():
    _identity, _runtime_instance = _runtime()
    role = RoleId("local-device", "p2")

    class FakeOutput:
        def __init__(self):
            self.calls = []
            self.expired = True
        def start(self):
            self.calls.append(("start",))
        def rearm(self):
            self.calls.append(("rearm",))
            self.expired = False
        def write(self, vector, *, elapsed_ms):
            if self.expired:
                raise RuntimeError("invalid_argument: Program session expired or was revoked")
            self.calls.append(("write", vector, elapsed_ms))
        def stop(self):
            self.calls.append(("stop",))

    output = FakeOutput()
    adapter = ProgramFollowOutput({role: output})
    adapter.arm(role)
    adapter.apply(FollowObservation(
        FollowState.PROGRAM_READY, role,
        RoleId("simulated-device", "remote-leader"), vector=(1.0, 0.0),
    ))
    assert output.calls == [("start",), ("rearm",), ("write", (1.0, 0.0), 20)]


def test_program_output_applies_registered_vector_transform_before_write():
    _identity, _runtime_instance = _runtime()
    role = RoleId("local-device", "p2")

    class FakeOutput:
        def __init__(self):
            self.calls = []
        def start(self): pass
        def write(self, vector, *, elapsed_ms): self.calls.append(vector)
        def stop(self): pass

    output = FakeOutput()
    adapter = ProgramFollowOutput(
        {role: output}, vector_transform=lambda vector: (vector[1], -vector[0]),
    )
    adapter.arm(role)
    adapter.apply(FollowObservation(
        FollowState.PROGRAM_READY,
        role,
        RoleId("simulated-device", "remote-leader"),
        vector=(1.0, 2.0),
    ))
    assert output.calls == [(2.0, -1.0)]


def test_program_output_close_all_closes_bound_outputs():
    _identity, _runtime_instance = _runtime()
    role = RoleId("local-device", "p2")

    class FakeOutput:
        def __init__(self):
            self.calls = []
        def start(self): self.calls.append("start")
        def write(self, vector, *, elapsed_ms): self.calls.append("write")
        def stop(self): self.calls.append("stop")
        def close(self): self.calls.append("close")

    output = FakeOutput()
    adapter = ProgramFollowOutput({role: output})
    adapter.arm(role)
    adapter.close_all()
    assert output.calls == ["start", "stop", "close"]


def test_simulated_follower_remains_fresh_inside_arrival_band():
    identity, runtime = _runtime()
    follower = RoleId("local-device", "p2")
    runtime.add_follower(follower, _position(follower, identity, (5, 5)), mode=ControlMode.SIMULATED)
    runtime.set_simulated_target((6, 6), now_ms=100)

    first = runtime.tick(now_ms=120)[follower.key]
    runtime.refresh_simulated_target(now_ms=1000)
    second = runtime.tick(now_ms=1000)[follower.key]

    assert first.state is FollowState.ARRIVED
    assert second.state is FollowState.ARRIVED


def test_unreachable_route_is_not_replanned_every_tick_but_retries_after_target_moves(monkeypatch):
    identity, runtime = _runtime()
    role = RoleId("local-device", "p2")
    runtime.add_follower(role, _position(role, identity, (5, 5)), mode=ControlMode.SIMULATED)
    runtime.set_simulated_target((50, 50), now_ms=100)
    attempts = []
    monkeypatch.setattr(runtime, "_plan_safe_route", lambda start, end: attempts.append((start, end)) or None)

    assert runtime.tick(now_ms=100)[role.key].state is FollowState.PREVIEWING
    runtime.refresh_simulated_target(now_ms=200)
    cooldown = runtime.tick(now_ms=200)[role.key]
    assert cooldown.state is FollowState.PREVIEWING
    assert cooldown.reason == "no_safe_route_probe"
    assert cooldown.vector != (0.0, 0.0)
    assert len(attempts) == 1
    runtime.set_simulated_target((35, 35), now_ms=220)
    assert runtime.tick(now_ms=220)[role.key].state is FollowState.PREVIEWING
    assert len(attempts) == 2
    runtime.refresh_simulated_target(now_ms=1500)
    assert runtime.tick(now_ms=1500)[role.key].state is FollowState.PREVIEWING
    assert len(attempts) == 3


def test_small_target_shift_replans_when_actor_reaches_old_route_endpoint():
    identity, runtime = _runtime()
    role = RoleId("local-device", "p2")
    runtime.add_follower(role, _position(role, identity, (5, 5)), mode=ControlMode.PREVIEW)
    runtime.set_simulated_target((20, 20), now_ms=100)
    first = runtime.tick(now_ms=100)[role.key]
    old_end = first.route[-1]

    runtime.update_follower_position(_position(role, identity, old_end, now=150))
    runtime.set_simulated_target((23, 20), now_ms=150)
    second = runtime.tick(now_ms=150)[role.key]

    assert second.state is FollowState.PREVIEWING
    assert second.vector != (0.0, 0.0)
    assert second.route[-1] != old_end


def test_blocked_route_retries_immediately_after_follower_moves(monkeypatch):
    identity, runtime = _runtime()
    role = RoleId("local-device", "p2")
    runtime.add_follower(role, _position(role, identity, (5, 5)), mode=ControlMode.PREVIEW)
    runtime.set_simulated_target((50, 50), now_ms=100)
    attempts = []
    monkeypatch.setattr(runtime, "_plan_safe_route", lambda start, end: attempts.append(start) or None)

    runtime.tick(now_ms=100)
    runtime.update_follower_position(_position(role, identity, (10, 5), now=150))
    runtime.tick(now_ms=150)

    assert attempts == [(5.0, 5.0), (10.0, 5.0)]


def test_target_shift_inside_old_arrival_band_still_advances_to_actual_target():
    identity, runtime = _runtime()
    role = RoleId("local-device", "p2")
    runtime.add_follower(role, _position(role, identity, (5, 5)), mode=ControlMode.PREVIEW)
    runtime.set_simulated_target((20, 20), now_ms=100)
    runtime.tick(now_ms=100)

    runtime.update_follower_position(_position(role, identity, (18.1, 20), now=150))
    runtime.set_simulated_target((21.5, 20), now_ms=150)
    observation = runtime.tick(now_ms=150)[role.key]

    assert observation.state is FollowState.PREVIEWING
    assert observation.vector != (0.0, 0.0)
    assert observation.route[-1] == (21.5, 20.0)


def test_small_target_motion_reuses_safe_route_until_refresh_band():
    identity, runtime = _runtime()
    role = RoleId("local-device", "p2")
    runtime.add_follower(role, _position(role, identity, (5, 5)), mode=ControlMode.PREVIEW)
    runtime.set_simulated_target((50, 50), now_ms=100)
    first = runtime.tick(now_ms=100)[role.key]
    assert first.route

    plan_calls = []
    original_plan = runtime._plan_safe_route

    def observe_plan(start, end):
        plan_calls.append((start, end))
        return original_plan(start, end)

    runtime._plan_safe_route = observe_plan
    runtime.update_follower_position(_position(role, identity, (6, 6), now=150))
    runtime.set_simulated_target((56, 56), now_ms=150)
    second = runtime.tick(now_ms=150)[role.key]

    assert second.vector != (0.0, 0.0)
    assert plan_calls == []
    assert second.diagnostics["route_target_shift"] == pytest.approx(8.485, abs=0.01)
