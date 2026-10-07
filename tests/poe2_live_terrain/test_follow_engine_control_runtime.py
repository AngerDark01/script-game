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
