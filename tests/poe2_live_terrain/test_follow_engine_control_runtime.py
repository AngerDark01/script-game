from __future__ import annotations

import time

from auto_modules.features.poe2.live_terrain.experimental.follow_engine.contracts import (
    ObservationSource,
    RoleVisualObservation,
    VisualObservation,
)
from auto_modules.features.poe2.live_terrain.experimental.follow_engine.control.follow_control_process import FollowControlRuntime
from auto_modules.features.poe2.live_terrain.experimental.follow_engine.generation import GenerationClock
from auto_modules.features.poe2.live_terrain.experimental.follow_engine.recovery.local_recovery import LocalRecoveryBackend
from auto_modules.features.poe2.live_terrain.experimental.follow_engine.recovery.memory_recovery import MemoryRecoveryBackend
from auto_modules.features.poe2.live_terrain.experimental.follow_engine.vision.local_roi_matcher import RoiMatch
from auto_modules.features.poe2.live_terrain.experimental.follow_engine.shared_frame_ring import SharedFrameRecord, SharedFrameRing
from auto_modules.features.poe2.live_terrain.experimental.follow_engine.execution_feedback import ExecutionReceipt


def _visual(sequence: int, p1=(0.0, 0.0), p2=(12.0, 0.0)) -> VisualObservation:
    return VisualObservation(
        generation=1,
        sequence=sequence,
        captured_at_ms=sequence * 33,
        map_instance="map-a",
        roles={
            "p1": RoleVisualObservation("p1", p1, confidence=1, uncertainty_native=1, visible=True, last_visual_at_ms=sequence * 33),
            "p2": RoleVisualObservation("p2", p2, confidence=1, uncertainty_native=1, visible=True, last_visual_at_ms=sequence * 33),
        },
        source=ObservationSource.VISUAL,
    )


def test_control_runtime_fuses_visual_and_emits_bounded_output_intents():
    token = GenerationClock().begin("map-a")
    runtime = FollowControlRuntime(token, {"p1": 1, "p2": 2})
    runtime.apply_visual(_visual(1))
    runtime.update_target("p2", (100, 0))
    snapshot = runtime.tick(now_ms=33)
    assert snapshot.session_active is True
    assert snapshot.output_intents[0].controller == 1
    p2 = next(item for item in snapshot.output_intents if item.role_id == "p2")
    assert p2.vector[0] > 0
    assert abs(p2.vector[0]) <= 1.0


def test_visual_gap_keeps_prediction_and_session_alive():
    token = GenerationClock().begin("map-a")
    runtime = FollowControlRuntime(token, {"p2": 2})
    runtime.apply_visual(_visual(1, p2=(10, 0)))
    runtime.update_target("p2", (100, 0))
    first = runtime.tick(now_ms=33)
    second = runtime.tick(now_ms=700)
    assert first.session_active and second.session_active
    assert second.recovery_state in {"visual_degraded", "predicting", "local_reanchor_pending"}
    assert second.output_intents[0].neutral is False


def test_rejected_visual_candidate_does_not_refresh_health_or_clear_misses():
    token = GenerationClock().begin("map-a")
    runtime = FollowControlRuntime(token, {"p2": 2})
    runtime.apply_visual(_visual(1, p2=(0, 0)))
    runtime.tick(now_ms=40)

    # The marker is visible in the frame, but the innovation is too large to
    # be accepted by the fusion gate.  It must not be treated as fresh
    # evidence merely because the candidate carries visible=True.
    runtime.apply_visual(_visual(2, p2=(100, 0)))
    snapshot = runtime.tick(now_ms=70)
    assert runtime._roles["p2"].misses > 0
    assert snapshot.recovery_reason != "visual_match"
    assert snapshot.roles["p2"].position_native == (0.0, 0.0)


def test_arrival_enters_follow_hold_without_releasing_session():
    token = GenerationClock().begin("map-a")
    runtime = FollowControlRuntime(token, {"p2": 2})
    runtime.apply_visual(_visual(1, p2=(10, 0)))
    runtime.update_target("p2", (15, 0))
    snapshot = runtime.tick(now_ms=33)
    assert snapshot.session_active is True
    assert snapshot.output_intents[0].neutral is True
    runtime.update_target("p2", (100, 0))
    next_snapshot = runtime.tick(now_ms=66)
    assert next_snapshot.output_intents[0].neutral is False


def test_predicted_arrival_keeps_an_unconfirmed_follow_pulse_alive():
    token = GenerationClock().begin("map-a")
    runtime = FollowControlRuntime(token, {"p2": 2})
    runtime.apply_visual(_visual(1, p2=(0, 0)))
    runtime.update_target("p2", (15, 0))
    first = runtime.tick(now_ms=0)
    second = runtime.tick(now_ms=80)
    assert first.output_intents[0].neutral is False
    assert second.output_intents[0].neutral is False
    assert second.output_intents[0].duration_ms > 0
    assert second.recovery_reason != "within_arrival_radius"
    assert second.output_intents[0].vector[0] > 0


def test_local_recovery_is_attempted_on_new_frame_before_memory():
    token = GenerationClock().begin("map-a")
    calls = []

    def search(_frame, point, radius):
        calls.append(radius)
        return RoiMatch(radius >= 80, (point[0] + 2, point[1] + 1), 0.9, radius, "accepted")

    runtime = FollowControlRuntime(
        token,
        {"p2": 2},
        local_recovery=LocalRecoveryBackend(),
        local_search=search,
    )
    runtime.apply_visual(_visual(1, p2=(10, 0)))
    missing = VisualObservation(
        generation=1,
        sequence=2,
        captured_at_ms=33,
        map_instance="map-a",
        roles={"p2": RoleVisualObservation("p2", None, visible=False, last_visual_at_ms=0)},
        source=ObservationSource.PARTIAL,
    )
    runtime.apply_visual(missing, frame="new-frame")
    snapshot = runtime.tick(now_ms=66)
    assert calls == [80.0]
    assert snapshot.recovery_reason == "local_recovered"
    assert snapshot.roles["p2"].source == "local_roi"


def test_local_recovery_does_not_override_conflicting_visible_frame_candidate():
    token = GenerationClock().begin("map-a")

    def search(_frame, point, radius):
        # Simulate a nearby role/static marker selected by the ROI while the
        # same frame contains a far, visible candidate for the tracked role.
        return RoiMatch(True, point, 0.95, radius, "accepted")

    runtime = FollowControlRuntime(
        token, {"p2": 2}, local_recovery=LocalRecoveryBackend(), local_search=search
    )
    runtime.apply_visual(_visual(1, p2=(0, 0)))
    runtime.tick(now_ms=40)
    runtime.apply_visual(_visual(2, p2=(100, 0)))
    snapshot = runtime.tick(now_ms=70)
    assert runtime._roles["p2"].misses > 0
    assert snapshot.roles["p2"].source != "local_roi"


def test_local_recovery_reads_new_frame_from_shared_ring_when_queue_has_metadata_only():
    ring = SharedFrameRing(capacity=2, slot_size=128, map_instance="map-a")
    try:
        token = GenerationClock().begin("map-a")
        calls = []

        def search(frame, point, radius):
            calls.append(frame)
            return RoiMatch(True, (point[0] + 1, point[1]), 0.9, radius, "accepted")

        runtime = FollowControlRuntime(
            token,
            {"p2": 2},
            frame_ring=ring,
            local_recovery=LocalRecoveryBackend(),
            local_search=search,
        )
        runtime.apply_visual(_visual(1, p2=(10, 0)))
        ring.publish(SharedFrameRecord(1, 2, 66, "map-a", b"encoded-frame"))
        missing = VisualObservation(
            generation=1,
            sequence=2,
            captured_at_ms=66,
            map_instance="map-a",
            roles={"p2": RoleVisualObservation("p2", None, visible=False, last_visual_at_ms=0)},
            source=ObservationSource.PARTIAL,
        )
        runtime.apply_visual(missing)
        snapshot = runtime.tick(now_ms=66)
        assert calls and calls[0].payload == b"encoded-frame"
        assert snapshot.recovery_reason == "local_recovered"
        runtime.close()
    finally:
        ring.close(unlink=True)


def test_two_role_local_recovery_is_round_robin_bounded_per_control_tick():
    token = GenerationClock().begin("map-a")
    calls = []

    def search(_frame, point, radius):
        calls.append(tuple(point))
        return RoiMatch(False, None, 0.0, radius, "miss")

    runtime = FollowControlRuntime(
        token,
        {"p1": 1, "p2": 2},
        local_recovery=LocalRecoveryBackend(),
        local_search=search,
    )
    runtime.apply_visual(_visual(1))
    missing = VisualObservation(
        generation=1,
        sequence=2,
        captured_at_ms=66,
        map_instance="map-a",
        roles={
            "p1": RoleVisualObservation("p1", None, visible=False),
            "p2": RoleVisualObservation("p2", None, visible=False),
        },
        source=ObservationSource.NONE,
    )
    runtime.apply_visual(missing, frame="frame")
    runtime.tick(now_ms=66)
    # LocalRoiMatcher may probe its bounded radius ladder, but only one role
    # is allowed to enter that ladder in a control tick.
    assert len(calls) == 3
    runtime.tick(now_ms=99)
    assert len(calls) == 6


def test_memory_recovery_is_submitted_async_and_seed_is_consumed_later():
    class Source:
        def read_many(self, expected_instance_id):
            return (
                type("Sample", (), {"identity": "p2", "grid": (20, 30), "area_instance": expected_instance_id})(),
            )

    token = GenerationClock().begin("map-a")
    backend = MemoryRecoveryBackend(Source(), transform=lambda point: (point[0] + 1, point[1] + 2), expected_players=1)
    runtime = FollowControlRuntime(token, {"p2": 2}, memory_recovery=backend)
    runtime.apply_visual(_visual(1, p2=(10, 0)))
    pending = runtime.tick(now_ms=2_000)
    assert pending.session_active is True
    assert pending.recovery_state == "memory_reanchor_pending"
    deadline = time.monotonic() + 2.0
    while time.monotonic() < deadline:
        recovered = runtime.tick(now_ms=2_033)
        if recovered.roles["p2"].source == "memory_reanchor":
            break
        time.sleep(0.01)
    else:
        raise AssertionError("memory recovery result was not consumed")
    assert recovered.session_active is True
    backend.close()


def test_transport_and_map_signals_keep_session_and_select_recovery_state():
    token = GenerationClock().begin("map-a")
    runtime = FollowControlRuntime(token, {"p2": 2})
    runtime.apply_visual(_visual(1, p2=(10, 0)))
    runtime.signal_recovery("host_session_expired")
    host_snapshot = runtime.tick(now_ms=33)
    assert host_snapshot.recovery_state == "follow_rearming"
    assert host_snapshot.session_active is True

    runtime.signal_recovery("map_changed")
    map_snapshot = runtime.tick(now_ms=66)
    assert map_snapshot.recovery_state == "global_reanchor_pending"
    assert map_snapshot.session_active is True


def test_observation_only_leader_is_fused_but_never_emits_controller_output():
    token = GenerationClock().begin("map-a")
    runtime = FollowControlRuntime(
        token,
        {"p2": 2},
        observation_role_ids=("p1", "p2"),
    )
    runtime.apply_visual(_visual(1, p1=(20, 20), p2=(10, 10)))
    runtime.update_target("p2", (100, 10))
    snapshot = runtime.tick(now_ms=33)
    assert set(snapshot.roles) == {"p1", "p2"}
    assert [intent.role_id for intent in snapshot.output_intents] == ["p2"]


def test_live_target_policy_updates_follower_in_same_visual_apply():
    """The control worker must not wait for a parent UI relay to refresh a target."""
    token = GenerationClock().begin("map-a")
    runtime = FollowControlRuntime(
        token,
        {"p2": 2},
        observation_role_ids=("p1", "p2"),
        live_target_source="p1",
        live_target_roles=("p2",),
        live_target_initial_position=(20.0, 20.0),
    )
    runtime.apply_visual(_visual(1, p1=(20, 20), p2=(10, 10)))
    assert runtime._roles["p2"].target == (20.0, 20.0)
    runtime.apply_visual(_visual(2, p1=(25, 20), p2=(10, 10)))
    assert runtime._roles["p2"].target == (22.5, 20.0)


def test_live_target_policy_rejects_untrusted_leader_candidate():
    token = GenerationClock().begin("map-a")
    runtime = FollowControlRuntime(
        token,
        {"p2": 2},
        observation_role_ids=("p1", "p2"),
        live_target_source="p1",
        live_target_roles=("p2",),
        live_target_initial_position=(20.0, 20.0),
    )
    runtime.apply_visual(_visual(1, p1=(20, 20), p2=(10, 10)))
    rejected = VisualObservation(
        generation=1,
        sequence=2,
        captured_at_ms=66,
        map_instance="map-a",
        roles={
            "p1": RoleVisualObservation("p1", (300, 300), confidence=1, uncertainty_native=1, visible=True),
            "p2": RoleVisualObservation("p2", (10, 10), confidence=1, uncertainty_native=1, visible=True),
        },
        source=ObservationSource.VISUAL,
    )
    runtime.apply_visual(rejected)
    assert runtime._roles["p2"].target == (20.0, 20.0)


def test_command_speed_is_calibrated_from_trusted_visual_displacement():
    token = GenerationClock().begin("map-a")
    runtime = FollowControlRuntime(token, {"p2": 2})
    runtime.apply_visual(_visual(1, p2=(0, 0)))
    runtime.update_target("p2", (100, 0))
    runtime.record_execution(ExecutionReceipt(1, 1, "p2", (0.65, 0.0), 0, 1000))
    runtime.tick(now_ms=0)

    # The real character moved only ten native units during the one-second
    # pulse.  The first visual correction is therefore allowed to teach the
    # predictor a slower speed instead of being rejected as a 42px innovation.
    late = VisualObservation(
        generation=1,
        sequence=2,
        captured_at_ms=1000,
        map_instance="map-a",
        roles={
            "p2": RoleVisualObservation(
                "p2", (10, 0), confidence=1, uncertainty_native=1,
                visible=True, last_visual_at_ms=1000,
            ),
        },
        source=ObservationSource.VISUAL,
    )
    runtime.apply_visual(late)
    snapshot = runtime.tick(now_ms=1000)
    role = runtime._roles["p2"]
    assert role.speed_calibrator is not None
    assert role.speed_calibrator.speed < 65.0
    assert snapshot.roles["p2"].source == "visual_fused"
