from __future__ import annotations

import cv2
import numpy as np

from auto_modules.features.poe2.live_terrain.experimental.follow_engine.vision.dual_association import DualRoleAssociator
from auto_modules.features.poe2.live_terrain.experimental.follow_engine.vision.local_roi_matcher import LocalRoiMatcher, RoiMatch
from auto_modules.features.poe2.live_terrain.experimental.follow_engine.vision.local_roi_search import EncodedMarkerRoiSearch
from auto_modules.features.poe2.live_terrain.experimental.follow_engine.vision.capture_adapter import CapturedFrame
from auto_modules.features.poe2.live_terrain.experimental.follow_engine.vision.marker_processor import extract_markers
from auto_modules.features.poe2.live_terrain.experimental.follow_engine.vision.wall_processor import process_wall
import auto_modules.features.poe2.live_terrain.experimental.follow_engine.vision.wall_processor as wall_processor
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


def test_wall_processor_normalizes_raw_phase_response_before_contract_export(monkeypatch):
    class Result:
        shift = (1.0, 0.0)
        quality = 1.37
        accepted = True
        reason = "accepted"

    monkeypatch.setattr(wall_processor, "estimate_bounded_displacement", lambda *args, **kwargs: Result())
    result = wall_processor.process_wall(np.zeros((8, 8), dtype=np.uint8), np.zeros((8, 8), dtype=np.uint8))
    assert result.quality == 1.0
    assert result.accepted is True


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


def test_encoded_marker_roi_search_decodes_only_the_requested_local_area():
    image = np.zeros((100, 100, 3), dtype=np.uint8)
    cv2.circle(image, (30, 40), 3, (0, 0, 255), -1)
    ok, encoded = cv2.imencode(".png", image)
    assert ok
    frame = CapturedFrame(1, 1, 33, "map-a", encoded.tobytes())
    search = EncodedMarkerRoiSearch()
    result = search(frame, (30, 40), 20)
    assert result is not None and result.valid is True
    assert result.position_native is not None
    assert np.linalg.norm(np.asarray(result.position_native) - np.asarray((30, 40))) < 5


def test_encoded_marker_roi_search_returns_no_candidate_outside_roi():
    image = np.zeros((100, 100, 3), dtype=np.uint8)
    cv2.circle(image, (30, 40), 3, (0, 0, 255), -1)
    ok, encoded = cv2.imencode(".png", image)
    assert ok
    frame = CapturedFrame(1, 1, 33, "map-a", encoded.tobytes())
    result = EncodedMarkerRoiSearch()(frame, (80, 80), 10)
    assert result is not None and result.valid is False


def test_encoded_marker_roi_search_prefers_nearest_candidate_over_farther_high_score(monkeypatch):
    image = np.zeros((100, 100, 3), dtype=np.uint8)
    ok, encoded = cv2.imencode(".png", image)
    assert ok
    frame = CapturedFrame(1, 1, 33, "map-a", encoded.tobytes())

    class Result:
        candidates = (
            PlayerMarkerCandidate("near", (30, 40), confidence=0.70),
            PlayerMarkerCandidate("far", (70, 40), confidence=1.0),
        )

    import auto_modules.features.poe2.live_terrain.experimental.follow_engine.vision.local_roi_search as module
    monkeypatch.setattr(module, "extract_markers", lambda *args, **kwargs: Result())
    result = EncodedMarkerRoiSearch()(frame, (30, 40), 50)
    assert result is not None and result.valid is True
    assert result.position_native == (30.0, 40.0)


def test_roi_excludes_large_area_and_other_role_before_nearest_selection(monkeypatch):
    from types import SimpleNamespace
    import auto_modules.features.poe2.live_terrain.experimental.follow_engine.vision.local_roi_search as module
    candidates = (
        PlayerMarkerCandidate("noise", (30, 40), confidence=1, area=80, color_features={"identity_hint": "orange"}),
        PlayerMarkerCandidate("other", (31, 40), confidence=1, area=32, color_features={"identity_hint": "blue"}),
        PlayerMarkerCandidate("correct", (45, 40), confidence=1, area=32, color_features={"identity_hint": "orange"}),
    )
    monkeypatch.setattr(module, "extract_markers", lambda *a, **kw: SimpleNamespace(candidates=candidates))
    search = EncodedMarkerRoiSearch(identity_hint="orange", decode_image=lambda _: np.zeros((100, 100, 3), dtype=np.uint8))
    result = search(b"image", (30, 40), 50)
    assert result.position_native == (45, 40)


def test_confirmation_expires_after_frame_gap_and_cannot_confirm_twice_in_one_frame():
    associator = DualRoleAssociator(base_gate=20, max_gate=40)
    candidates = [PlayerMarkerCandidate("a", (100, 0), confidence=1, color_features={"identity_hint": "orange"})]
    def assign(stamp):
        return associator.assign(candidates, {"p1": (0, 0)}, identity_hints={"p1": "orange"}, captured_at_ms=stamp)
    assert not assign(100).assignments
    assert not assign(100).assignments
    assert not assign(2000).assignments
    assert assign(2033).assignments == {"p1": (100, 0)}
