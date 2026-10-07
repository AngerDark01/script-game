from __future__ import annotations

import math

import pytest

from auto_modules.features.poe2.live_terrain.experimental.follow_engine.contracts import (
    FrameSlot,
    FrameSlotStatus,
    FusionSnapshot,
    ObservationSource,
    OutputIntent,
    PredictionSnapshot,
    RoleFusedState,
    RolePrediction,
    RoleVisualObservation,
    StageTiming,
    VisualObservation,
)


def _visual(role: str, position: tuple[float, float] | None) -> RoleVisualObservation:
    return RoleVisualObservation(
        role_id=role,
        position_native=position,
        velocity_native=(1.0, 0.0),
        confidence=0.9 if position else 0.0,
        uncertainty_native=2.0,
        visible=position is not None,
        last_visual_at_ms=100 if position else None,
    )


def test_contracts_are_immutable_and_validate_process_headers():
    timing = StageTiming(capture_ms=1, marker_ms=2, total_ms=3)
    observation = VisualObservation(
        generation=4,
        sequence=8,
        captured_at_ms=100,
        map_instance="map-a",
        roles={"p1": _visual("p1", (10, 20)), "p2": _visual("p2", None)},
        source=ObservationSource.PARTIAL,
        timing=timing,
    )
    assert observation.roles["p1"].position_native == (10.0, 20.0)
    assert observation.timing.total_ms == 3.0
    with pytest.raises(TypeError):
        observation.roles["p1"] = _visual("p1", (0, 0))

    slot = FrameSlot(4, 8, 100, "map-a", 200, 200, 0, 40000, FrameSlotStatus.READY)
    assert slot.status is FrameSlotStatus.READY


def test_prediction_fusion_and_output_contracts_are_bounded():
    prediction = RolePrediction("p2", (10, 20), (1, 0), 4, "command_prediction", 80, 40)
    snapshot = PredictionSnapshot(4, 9, 140, {"p2": prediction}, calibration_confidence=0.8)
    fused = RoleFusedState("p2", (11, 20), (1, 0), 3, "fused", 20)
    intent = OutputIntent("p2", 2, (0.5, -0.5), 50)
    result = FusionSnapshot(
        generation=4,
        created_at_ms=150,
        roles={"p2": fused},
        recovery_state="tracking",
        recovery_reason="visual_ok",
        control_vectors={"p2": intent.vector},
        output_intents=(intent,),
    )
    assert snapshot.roles["p2"].uncertainty_native == 4.0
    assert result.output_intents[0].controller == 2
    assert all(math.isfinite(value) for value in result.control_vectors["p2"])


@pytest.mark.parametrize(
    "factory",
    [
        lambda: StageTiming(capture_ms=-1),
        lambda: FrameSlot(1, 1, 0, "map", 0, 10, 0, 1),
        lambda: _visual("p1", (float("nan"), 1)),
        lambda: OutputIntent("p2", 2, (2, 0), 10),
        lambda: VisualObservation(1, 1, 1, "map", {"p1": _visual("other", (1, 1))}),
    ],
)
def test_contracts_reject_invalid_values(factory):
    with pytest.raises((TypeError, ValueError)):
        factory()
