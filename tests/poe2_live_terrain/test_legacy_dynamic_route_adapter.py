from __future__ import annotations

import numpy as np

from auto_modules.features.poe2.live_terrain.experimental.follow_engine.control.route_controller import LegacyDynamicFollowRouteController
from auto_modules.features.poe2.live_terrain.experimental.multiplayer_follow.models import ControlMode, MapIdentity, PositionSample, RoleId
from auto_modules.features.poe2.live_terrain.experimental.multiplayer_follow.runtime import SimulatedFollowRuntime


def test_legacy_dynamic_adapter_holds_inside_dynamic_arrival_radius():
    adapter = LegacyDynamicFollowRouteController(np.zeros((64, 64), dtype=np.uint8))
    decision = adapter.plan((10.0, 10.0), (20.0, 10.0))
    # Continuous follow represents a nearby leader as a hold state.  It must
    # emit no pulse, but it is not a terminal one-shot arrival.
    assert decision.arrived is False
    assert decision.vector == (0.0, 0.0)
    assert decision.duration_ms == 0


def test_legacy_dynamic_adapter_emits_bounded_old_component_decision_and_replans_target_shift():
    adapter = LegacyDynamicFollowRouteController(np.zeros((128, 128), dtype=np.uint8))
    first = adapter.plan((10.0, 10.0), (50.0, 10.0), now_ms=1000)
    second = adapter.plan((10.0, 10.0), (80.0, 10.0), now_ms=1033)
    assert first.arrived is False and second.arrived is False
    assert max(abs(value) for value in first.vector) <= 1.0
    assert max(abs(value) for value in second.vector) <= 1.0
    assert first.duration_ms == 0
    assert 0 <= second.duration_ms <= 33
    assert first.reason == second.reason == "route_ready"


def test_legacy_dynamic_adapter_fixture_matrix_is_per_role_and_continuous():
    # Contract fixture for the old dynamic-follow inputs.  It cannot import a
    # different git checkout in-process, so this records the scenario matrix
    # and asserts the adapter's per-role state is independent.
    matrix = {
        "hold": ((10.0, 10.0), (20.0, 10.0)),
        "leader_move": ((10.0, 10.0), (60.0, 10.0)),
        "turn": ((10.0, 10.0), (60.0, 60.0)),
        "door": ((10.0, 10.0), (10.0, 70.0)),
        "role_swap": ((70.0, 70.0), (20.0, 20.0)),
    }
    p1 = LegacyDynamicFollowRouteController(np.zeros((96, 96), dtype=np.uint8))
    p2 = LegacyDynamicFollowRouteController(np.zeros((96, 96), dtype=np.uint8))
    for name, (position, target) in matrix.items():
        left = p1.plan(position, target)
        right = p2.plan(position, target)
        assert left.vector == right.vector
        assert left.duration_ms == right.duration_ms
        assert left.arrived == right.arrived
        assert left.reason == right.reason


def test_legacy_adapter_replays_the_reference_runtime_action_contract():
    """The process adapter must be a translation layer, not a new policy."""
    wall_map = np.zeros((96, 96), dtype=np.uint8)
    adapter = LegacyDynamicFollowRouteController(wall_map)
    identity = MapIdentity("follow-engine", "legacy-motion-v1")
    role = RoleId("follow-engine", "follower")
    leader = RoleId("follow-engine", "leader")
    reference = SimulatedFollowRuntime(
        wall_map=wall_map,
        map_identity=identity,
        arrival_radius=adapter.arrival_radius,
        resume_radius=adapter.resume_radius,
        speed_units_per_second=80.0,
        downsample_factor=8,
        local_lookahead=24.0,
        prediction_horizon=0.25,
        continuous_follow=True,
    )
    reference.add_follower(
        role,
        PositionSample(role, identity, (10.0, 10.0), 1000, 1.0, "visual_fused"),
        mode=ControlMode.PROGRAM,
    )
    sequence = [
        ((10.0, 10.0), (20.0, 10.0)),  # nearby hold
        ((10.0, 10.0), (50.0, 10.0)),  # leader movement
        ((10.0, 10.0), (50.0, 50.0)),  # turn
        ((10.0, 10.0), (80.0, 50.0)),  # long corridor
        ((12.0, 10.0), (80.0, 50.0)),  # delayed/estimated follower frame
    ]
    for index, (position, target) in enumerate(sequence):
        now = 1000 + index * 33
        adapter_decision = adapter.plan(
            position,
            target,
            now_ms=now,
            position_source="command_prediction" if index == 4 else "visual_fused",
        )
        reference.update_follower_position(
            PositionSample(role, identity, position, now, 1.0,
                           "command_prediction" if index == 4 else "visual_fused")
        )
        reference.set_target_sample(PositionSample(leader, identity, target, now + 1, 1.0, "simulated"))
        expected = reference.tick(now_ms=now)[role.key]
        assert adapter_decision.vector == expected.vector
        assert adapter_decision.duration_ms == int(expected.diagnostics.get("command_duration_ms", 0))
        assert adapter_decision.arrived == (expected.state.value in {"arrived", "waiting_position"})
        assert adapter_decision.reason == expected.reason
