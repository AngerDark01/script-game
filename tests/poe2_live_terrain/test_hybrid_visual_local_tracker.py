from types import SimpleNamespace

import cv2
import numpy as np
import pytest

from auto_modules.core.localization import LocalizationResult
from auto_modules.core.localization.canonical_wall import canonical_wall_mask
from auto_modules.features.poe2.live_terrain.experimental.hybrid_localization.local_tracker import (
    VisualLocalTracker,
)
from auto_modules.features.poe2.live_terrain.experimental.hybrid_localization.models import (
    AbsoluteRegistration,
    HybridFrame,
    SimilarityTransform2D,
)
from auto_modules.features.poe2.live_terrain.experimental.hybrid_localization.similarity_search import (
    transform_feature,
)


class MatcherFake:
    def __init__(self, result):
        self.result = result
        self.calls = []

    def match(self, walls, *, origin, radius, scale=1.0):
        self.calls.append((walls, origin, radius, scale))
        return self.result


def make_frame(frame_id: int, player=(20.0, 18.0)):
    walls = np.zeros((48, 64), dtype=np.uint8)
    cv2.line(walls, (2, 7), (50, 7), 255, 2)
    cv2.line(walls, (50, 7), (50, 40), 255, 2)
    return HybridFrame(frame_id, frame_id * 100, walls, player)


def make_previous():
    return AbsoluteRegistration(
        result=LocalizationResult((130.0, 230.0), 0.9, source="anchored_absolute"),
        transform=SimilarityTransform2D(45.0, True, 1.2, (100.0, 200.0)),
        anchor_error=2.0,
        area_instance="Map:A1",
    )


def test_local_tracker_keeps_similarity_transform_and_updates_translation():
    previous_frame = HybridFrame(
        1,
        100,
        np.zeros((48, 64), dtype=np.uint8),
        (20.0, 18.0),
    )
    frame = make_frame(2)
    matcher = MatcherFake(
        SimpleNamespace(
            valid=True,
            frame_origin_global=(105.0, 198.0),
            confidence=0.82,
            metadata={"candidate_margin": 0.4},
        )
    )
    tracker = VisualLocalTracker(matcher, search_radius=32.0)

    result = tracker.track(
        frame,
        reference=object(),
        previous_frame=previous_frame,
        previous=make_previous(),
    )

    assert result is not None
    transformed = transform_feature(
        canonical_wall_mask(frame.wall_mask),
        frame.local_player,
        angle=45.0,
        reflect_horizontal=True,
        scale=1.2,
    )
    assert result.result.position == pytest.approx(
        (
            105.0 + transformed.player_position[0],
            198.0 + transformed.player_position[1],
        )
    )
    assert result.result.source == "visual_local"
    assert result.transform.angle_degrees == 45.0
    assert result.transform.reflect_horizontal is True
    assert result.transform.scale == 1.2
    assert result.transform.translation == (105.0, 198.0)
    assert matcher.calls[0][1:] == ((100.0, 200.0), 32.0, 1.0)
    assert np.array_equal(matcher.calls[0][0], transformed.mask)


@pytest.mark.parametrize(
    "candidate",
    [
        SimpleNamespace(valid=False),
        SimpleNamespace(valid=True, frame_origin_global=None, confidence=0.9, metadata={}),
    ],
)
def test_local_tracker_fails_closed_on_invalid_bounded_match(candidate):
    matcher = MatcherFake(candidate)
    tracker = VisualLocalTracker(matcher)
    previous_frame = HybridFrame(
        1,
        100,
        np.zeros((48, 64), dtype=np.uint8),
        (20.0, 18.0),
    )

    result = tracker.track(
        make_frame(2),
        reference=object(),
        previous_frame=previous_frame,
        previous=make_previous(),
    )

    assert result is None
    assert len(matcher.calls) == 1


def test_local_tracker_uses_f2f_displacement_without_shape_match():
    previous = make_frame(1)
    current_mask = np.roll(np.roll(previous.wall_mask, -3, axis=0), 4, axis=1)
    current = HybridFrame(2, 200, current_mask, previous.local_player)
    matcher = MatcherFake(SimpleNamespace(valid=False))
    tracker = VisualLocalTracker(matcher)

    result = tracker.track(
        current,
        reference=object(),
        previous_frame=previous,
        previous=make_previous(),
    )

    assert result is not None
    assert result.result.source == "visual_f2f"
    assert result.result.position == pytest.approx(
        (
            make_previous().result.position[0] - result.diagnostics["global_shift"][0],
            make_previous().result.position[1] - result.diagnostics["global_shift"][1],
        )
    )
    assert matcher.calls == []


def test_local_tracker_replays_continuous_motion_without_shape_matching():
    matcher = MatcherFake(SimpleNamespace(valid=False))
    tracker = VisualLocalTracker(matcher)
    previous_frame = make_frame(1)
    previous_registration = make_previous()
    positions = []

    for frame_id, (dx, dy) in enumerate(((2, 1), (4, 2), (6, 3)), start=2):
        current_mask = np.roll(np.roll(previous_frame.wall_mask, -dy, axis=0), dx, axis=1)
        current = HybridFrame(frame_id, frame_id * 100, current_mask, previous_frame.local_player)
        result = tracker.track(
            current,
            reference=object(),
            previous_frame=previous_frame,
            previous=previous_registration,
        )
        assert result is not None
        assert result.result.source == "visual_f2f"
        positions.append(result.result.position)
        previous_frame = current
        previous_registration = result

    assert len(matcher.calls) == 0
    assert positions[-1] != make_previous().result.position


def test_local_tracker_periodically_corrects_motion_with_bounded_shape_match():
    matcher = MatcherFake(
        SimpleNamespace(
            valid=True,
            frame_origin_global=(104.0, 199.0),
            confidence=0.88,
            metadata={"mean_wall_error_px": 0.4},
        )
    )
    tracker = VisualLocalTracker(
        matcher,
        correction_frame_interval=1,
        correction_distance=24.0,
        correction_interval_ms=1500,
    )
    previous_frame = make_frame(1)
    current_mask = np.roll(np.roll(previous_frame.wall_mask, -2, axis=0), 3, axis=1)
    current = HybridFrame(2, 200, current_mask, previous_frame.local_player)

    result = tracker.track(
        current,
        reference=object(),
        previous_frame=previous_frame,
        previous=make_previous(),
    )

    assert result is not None
    assert result.result.source == "visual_local"
    assert result.result.metadata["correction_attempted"] is True
    assert result.result.metadata["correction_accepted"] is True
    assert result.result.metadata["last_correction_frame_id"] == 2
    assert len(matcher.calls) == 1


def test_local_tracker_does_not_correct_static_frames():
    matcher = MatcherFake(SimpleNamespace(valid=False))
    tracker = VisualLocalTracker(matcher, correction_frame_interval=1, correction_interval_ms=1)
    previous_frame = make_frame(1)
    current = HybridFrame(2, 200, previous_frame.wall_mask.copy(), previous_frame.local_player)

    result = tracker.track(
        current,
        reference=object(),
        previous_frame=previous_frame,
        previous=make_previous(),
    )

    assert result is not None
    assert result.result.source == "visual_f2f"
    assert result.result.metadata["correction_due"] is False
    assert matcher.calls == []


def test_local_tracker_keeps_prediction_when_periodic_correction_fails():
    matcher = MatcherFake(SimpleNamespace(valid=False))
    tracker = VisualLocalTracker(matcher, correction_frame_interval=1)
    previous_frame = make_frame(1)
    current_mask = np.roll(np.roll(previous_frame.wall_mask, -2, axis=0), 3, axis=1)
    current = HybridFrame(2, 200, current_mask, previous_frame.local_player)

    result = tracker.track(
        current,
        reference=object(),
        previous_frame=previous_frame,
        previous=make_previous(),
    )

    assert result is not None
    assert result.result.source == "visual_f2f"
    assert result.result.metadata["correction_attempted"] is True
    assert result.result.metadata["correction_accepted"] is False
    assert result.result.metadata["correction_reason"] == "bounded_match_failed"
    assert len(matcher.calls) == 1

    next_frame = HybridFrame(3, 300, current_mask.copy(), current.local_player)
    next_result = tracker.track(
        next_frame,
        reference=object(),
        previous_frame=current,
        previous=result,
    )
    assert next_result is not None
    assert len(matcher.calls) == 1
