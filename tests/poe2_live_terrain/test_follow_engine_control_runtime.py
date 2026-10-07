from __future__ import annotations

from auto_modules.features.poe2.live_terrain.experimental.follow_engine.contracts import (
    ObservationSource,
    RoleVisualObservation,
    VisualObservation,
)
from auto_modules.features.poe2.live_terrain.experimental.follow_engine.control.follow_control_process import FollowControlRuntime
from auto_modules.features.poe2.live_terrain.experimental.follow_engine.generation import GenerationClock


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
