from dataclasses import FrozenInstanceError
from types import SimpleNamespace

import numpy as np
import pytest

from auto_modules.core.localization import LocalizationResult
from auto_modules.features.poe2.live_terrain.experimental.hybrid_localization.models import (
    AbsoluteRegistration,
    HybridFrame,
    HybridLocalizationMode,
    HybridLocalizationState,
    PositionAnchor,
    SimilarityTransform2D,
)


def test_anchor_and_transform_are_finite_immutable_values():
    anchor = PositionAnchor((12.5, 20.0), "Map:A1", 1000, "memory")
    transform = SimilarityTransform2D(219.0, True, 0.85, (4.0, 8.0))

    assert anchor.position == (12.5, 20.0)
    assert transform.scale == 0.85
    assert HybridLocalizationMode.NEED_ABSOLUTE.value == "need_absolute"
    with pytest.raises(FrozenInstanceError):
        anchor.source = "other"


@pytest.mark.parametrize("position", [(float("nan"), 1.0), (1.0, float("inf"))])
def test_anchor_rejects_non_finite_position(position):
    with pytest.raises(ValueError, match="finite"):
        PositionAnchor(position, "Map:A1", 1000, "memory")


def test_frame_and_state_snapshot_mutable_inputs():
    mask = np.array([[0, 255], [255, 0]], dtype=np.uint8)
    frame = HybridFrame(
        frame_id=7,
        captured_at_ms=1000,
        wall_mask=mask,
        local_player=(1.0, 1.0),
    )
    transform = SimilarityTransform2D(45.0, False, 1.0, (5.0, 6.0))
    registration = AbsoluteRegistration(
        result=LocalizationResult((6.0, 7.0), 0.9, source="anchored_absolute"),
        transform=transform,
        anchor_error=0.5,
        area_instance="Map:A1",
        diagnostics={"score": 0.9},
    )
    state = HybridLocalizationState(
        mode=HybridLocalizationMode.LOCAL_TRACKING,
        position=(6.0, 7.0),
        latest_confirmed_position=(6.0, 7.0),
        trajectory=((6.0, 7.0),),
        registration=registration,
        source="anchored_absolute",
        confidence=0.9,
        reason="",
        recovery_revision=1,
    )

    mask[:] = 0
    assert frame.wall_mask[0, 1] == 255
    assert frame.wall_mask.flags.writeable is False
    assert registration.diagnostics["score"] == 0.9
    assert state.position == (6.0, 7.0)


def test_frame_from_evidence_preserves_real_capture_size_diagnostic():
    evidence = SimpleNamespace(
        wall_mask=np.zeros((320, 320), dtype=np.uint8),
        feature=None,
        monitor_config={
            "capture_size": 320,
            "binding": {"player_marker_position": [160, 160]},
        },
        captured_at="2026-09-23T00:00:00+00:00",
    )

    frame = HybridFrame.from_evidence(evidence, captured_at_ms=1000, frame_id=1)

    assert frame.local_player == (160.0, 160.0)
    assert frame.diagnostics["capture_size"] == 320


@pytest.mark.parametrize(
    ("factory", "message"),
    [
        (lambda: PositionAnchor((1.0, 2.0), "", 1000, "memory"), "area_instance"),
        (
            lambda: SimilarityTransform2D(0.0, False, 0.0, (0.0, 0.0)),
            "positive",
        ),
        (
            lambda: HybridFrame(1, -1, np.ones((2, 2), dtype=np.uint8), (1.0, 1.0)),
            "non-negative",
        ),
    ],
)
def test_models_reject_invalid_contract_values(factory, message):
    with pytest.raises(ValueError, match=message):
        factory()
