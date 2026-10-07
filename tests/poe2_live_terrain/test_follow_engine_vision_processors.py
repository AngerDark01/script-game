from __future__ import annotations

import cv2
import numpy as np

from auto_modules.features.poe2.live_terrain.experimental.follow_engine.vision.dual_association import DualRoleAssociator
from auto_modules.features.poe2.live_terrain.experimental.follow_engine.vision.local_roi_matcher import LocalRoiMatcher, RoiMatch
from auto_modules.features.poe2.live_terrain.experimental.follow_engine.vision.marker_processor import extract_markers
from auto_modules.features.poe2.live_terrain.experimental.follow_engine.vision.wall_processor import process_wall
from auto_modules.features.poe2.live_terrain.experimental.multiplayer_localization.models import PlayerMarkerCandidate


def test_wall_processor_returns_bounded_displacement_and_rejects_shape_change():
    previous = np.zeros((80, 80), dtype=np.uint8)
    cv2.rectangle(previous, (20, 20), (50, 50), 255, 2)
    current = np.roll(previous, 2, axis=1)
    result = process_wall(previous, current, max_shift=10)
    assert result.accepted is True
    assert result.shift is not None
    rejected = process_wall(previous, np.zeros((40, 40), dtype=np.uint8))
    assert rejected.accepted is False
    assert rejected.reason == "shape_mismatch"


def test_marker_processor_extracts_compact_colored_candidates():
    image = np.zeros((100, 100, 3), dtype=np.uint8)
    cv2.circle(image, (30, 40), 3, (0, 0, 255), -1)
    cv2.circle(image, (70, 60), 3, (0, 255, 255), -1)
    result = extract_markers(image, 100)
    assert len(result.candidates) >= 2
    assert result.raw_candidate_count >= len(result.candidates)


def test_dual_association_uses_motion_and_pair_geometry_with_soft_color():
    candidates = (
        PlayerMarkerCandidate("a", (101, 100), confidence=0.9, color_features={"identity_hint": "blue"}),
        PlayerMarkerCandidate("b", (200, 100), confidence=0.8, color_features={"identity_hint": "blue"}),
    )
    result = DualRoleAssociator(base_gate=20, max_gate=80).assign(
        candidates,
        {"p1": (100, 100), "p2": (201, 100)},
        identity_hints={"p1": "orange", "p2": "blue"},
        elapsed_ms={"p1": 33, "p2": 33},
    )
    assert result.ambiguous is False
    assert set(result.assignments) == {"p1", "p2"}


def test_local_roi_matcher_expands_radius_without_stopping_session():
    calls = []

    def search(_frame, point, radius):
        calls.append(radius)
        if radius < 140:
            return RoiMatch(False, None, 0.2, radius, "weak")
        return RoiMatch(True, (point[0] + 2, point[1]), 0.8, radius, "accepted")

    result = LocalRoiMatcher().match(object(), (10, 20), search)
    assert result.valid is True
    assert calls == [80.0, 140.0]
