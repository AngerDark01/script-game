from __future__ import annotations

import numpy as np

from auto_modules.core.localization import LocalizationResult
from auto_modules.core.localization.observations import (
    ObservationCandidate,
    ObservationFrame,
)
from auto_modules.features.poe2.live_terrain.experimental.hybrid_localization.absolute_registrar import (
    AnchoredAbsoluteRegistrar,
)
from auto_modules.features.poe2.live_terrain.experimental.hybrid_localization.models import (
    AbsoluteRegistration,
    HybridFrame,
    PositionAnchor,
    SimilarityTransform2D,
)
from auto_modules.features.poe2.live_terrain.experimental.hybrid_localization.similarity_search import (
    transform_feature,
    transform_local_point,
)
from auto_modules.features.poe2.live_terrain.experimental.multiplayer_localization import (
    DualFirstFrameExperiment,
    DualFirstFrameRegistrar,
    MarkerColorProfile,
    PlayerMarkerCandidate,
    Poe2DualMemoryAnchorProvider,
    Poe2EntityPositionSample,
    build_poe2_dual_first_frame_registrar,
    detect_saturated_marker_observation,
    marker_candidates_from_observation,
)
from auto_modules.features.poe2.live_terrain.experimental.multiplayer_localization.dual_first_frame import (
    _joint_similarity_estimates,
    _reference_match_terrain,
)
from auto_modules.features.poe2.live_terrain.orientation import TerrainOrientation
from auto_modules.features.poe2.live_terrain.terrain_reference import TerrainReference


class _FakeRegistrar:
    def __init__(self, *, expected_primary, registration):
        self.expected_primary = expected_primary
        self.registration = registration
        self.last_diagnostics = {"status": "rejected", "reason": "fake primary mismatch"}

    def register(self, frame, *, reference, anchor):
        if frame.local_player != self.expected_primary:
            return None
        return self.registration


def test_marker_candidates_preserve_one_candidate_per_configured_profile():
    observation = ObservationFrame(
        captured_at_ms=1,
        candidates=(
            ObservationCandidate((10, 10), 0.99, identity_hint="p1", evidence={"profile_index": 0}),
            ObservationCandidate((11, 10), 0.98, identity_hint="p1", evidence={"profile_index": 0}),
            ObservationCandidate((25, 25), 0.80, identity_hint="p2", evidence={"profile_index": 1}),
        ),
        source="test",
    )
    candidates = marker_candidates_from_observation(observation)
    assert {candidate.local_position for candidate in candidates} == {(10.0, 10.0), (25.0, 25.0)}


def test_marker_candidates_suppress_outline_core_duplicate_but_keep_close_players():
    observation = ObservationFrame(
        captured_at_ms=1,
        candidates=(
            ObservationCandidate(
                (10, 10), 0.99, evidence={"profile_index": 0, "bbox": [7, 7, 7, 7]}
            ),
            ObservationCandidate(
                (11, 10), 0.91, evidence={"profile_index": 0, "bbox": [8, 8, 5, 5]}
            ),
            ObservationCandidate(
                (15, 10), 0.88, evidence={"profile_index": 0, "bbox": [12, 7, 7, 7]}
            ),
        ),
    )

    candidates = marker_candidates_from_observation(observation)

    assert len(candidates) == 2
    assert candidates[0].local_position == (10.0, 10.0)
    assert candidates[1].local_position == (15.0, 10.0)


def test_marker_candidates_keep_close_different_profiles_even_when_boxes_overlap():
    observation = ObservationFrame(
        captured_at_ms=1,
        candidates=(
            ObservationCandidate(
                (10, 10), 0.99, evidence={"profile_index": 0, "bbox": [7, 7, 7, 7]}
            ),
            ObservationCandidate(
                (11, 10), 0.98, evidence={"profile_index": 1, "bbox": [8, 8, 7, 7]}
            ),
        ),
    )

    candidates = marker_candidates_from_observation(observation)

    assert len(candidates) == 2
    assert {candidate.color_features["profile_index"] for candidate in candidates} == {0, 1}


class _RecordingRegistrar:
    def __init__(self, registration):
        self.registration = registration
        self.last_diagnostics = {"status": "rejected", "reason": "fake primary mismatch"}
        self.calls = []

    def register(self, frame, *, reference, anchor):
        self.calls.append((frame.local_player, anchor.position))
        return self.registration


def _fixture(*, second_offset=(0.0, 0.0)):
    feature = np.zeros((100, 120), dtype=np.uint8)
    transform = SimilarityTransform2D(
        angle_degrees=37.0,
        reflect_horizontal=True,
        scale=1.1,
        translation=(80.0, 120.0),
    )
    p1 = (20.0, 30.0)
    p2 = (75.0, 62.0)
    m1 = transform_local_point(
        feature.shape,
        p1,
        angle=transform.angle_degrees,
        reflect_horizontal=transform.reflect_horizontal,
        scale=transform.scale,
        translation=transform.translation,
    )
    m2 = transform_local_point(
        feature.shape,
        p2,
        angle=transform.angle_degrees,
        reflect_horizontal=transform.reflect_horizontal,
        scale=transform.scale,
        translation=transform.translation,
    )
    m2 = (m2[0] + second_offset[0], m2[1] + second_offset[1])
    anchors = {
        "p1": PositionAnchor(m1, "Area:1", 100, "memory"),
        "p2": PositionAnchor(m2, "Area:1", 100, "memory"),
    }
    registration = AbsoluteRegistration(
        result=LocalizationResult(m1, 0.90, source="fake", registration_valid=True),
        transform=transform,
        anchor_error=0.0,
        area_instance="Area:1",
        diagnostics={"confidence": 0.90},
    )
    frame = HybridFrame(
        frame_id=1,
        captured_at_ms=100,
        wall_mask=feature,
        local_player=p1,
        diagnostics={"capture_size": 100},
    )
    candidates = (
        PlayerMarkerCandidate("marker-p1", p1, confidence=0.95),
        PlayerMarkerCandidate("marker-p2", p2, confidence=0.92),
    )
    reference = TerrainReference(
        walkable_mask=np.ones((300, 300), dtype=bool),
        wall_layer=np.zeros((300, 300), dtype=np.uint8),
        explored_map=np.full((300, 300), 255, dtype=np.uint8),
        width=300,
        height=300,
        metadata={"instance_id": "Area:1"},
    )
    return frame, reference, anchors, candidates, registration


def test_transform_local_point_matches_transformed_feature_player_projection():
    frame, _reference, _anchors, candidates, _registration = _fixture()
    transformed = transform_feature(
        frame.wall_mask,
        candidates[0].local_position,
        angle=37.0,
        reflect_horizontal=True,
        scale=1.1,
    )
    projected = transform_local_point(
        frame.wall_mask.shape,
        candidates[0].local_position,
        angle=37.0,
        reflect_horizontal=True,
        scale=1.1,
    )
    assert projected == transformed.player_position


def test_dual_first_frame_accepts_two_markers_with_one_transform_even_when_reversed():
    frame, reference, anchors, candidates, registration = _fixture()
    registrar = DualFirstFrameRegistrar(
        _FakeRegistrar(expected_primary=candidates[0].local_position, registration=registration)
    )

    result = registrar.register(
        frame,
        reference=reference,
        anchors=anchors,
        candidates=tuple(reversed(candidates)),
    )

    assert result.status == "accepted"
    assert result.players["p1"].candidate_id == "marker-p1"
    assert result.players["p2"].candidate_id == "marker-p2"
    assert result.players["p1"].anchor_error == 0.0
    assert result.players["p2"].anchor_error == 0.0
    assert result.diagnostics["evaluated_assignment_count"] == 1
    assert result.diagnostics["joint_initialization"]["pair_mode"] == "direct_pair"


def test_dual_first_frame_accepts_exact_anchors_when_wall_coverage_is_sparse():
    frame, reference, anchors, candidates, registration = _fixture()
    sparse = AbsoluteRegistration(
        result=LocalizationResult(
            anchors["p1"].position,
            0.48,
            source="sparse",
            registration_valid=True,
        ),
        transform=registration.transform,
        anchor_error=0.0,
        area_instance="Area:1",
        diagnostics={"joint_shape_coverage": 0.48},
    )
    result = DualFirstFrameRegistrar(
        _FakeRegistrar(expected_primary=candidates[0].local_position, registration=sparse)
    ).register(frame, reference=reference, anchors=anchors, candidates=candidates)

    assert result.status == "accepted"
    assert result.diagnostics["best_pair_confidence"] >= 0.80
    assert result.diagnostics["joint_initialization"]["shape_quality"] == 0.48


def test_dual_first_frame_rejects_when_second_anchor_is_not_explained():
    frame, reference, anchors, candidates, registration = _fixture(second_offset=(20.0, 0.0))
    registrar = DualFirstFrameRegistrar(
        _FakeRegistrar(expected_primary=candidates[0].local_position, registration=registration)
    )

    result = registrar.register(
        frame,
        reference=reference,
        anchors=anchors,
        candidates=candidates,
    )

    assert result.status == "rejected"
    assert "both memory anchors" in result.reason
    assert result.diagnostics["failed_assignments"]


def test_dual_first_frame_requires_two_candidates_without_touching_single_frame_contract():
    frame, reference, anchors, candidates, registration = _fixture()
    registrar = DualFirstFrameRegistrar(
        _FakeRegistrar(expected_primary=candidates[0].local_position, registration=registration)
    )

    result = registrar.register(
        frame,
        reference=reference,
        anchors=anchors,
        candidates=candidates[:1],
    )

    assert result.status == "insufficient"
    assert "exactly two minimap marker candidates" in result.reason


def test_dual_registrar_does_not_inherit_single_player_feature_masks():
    registrar = DualFirstFrameRegistrar()

    assert registrar.registrar.config.player_clear_radius == 0
    assert registrar.registrar.config.top_exclusion_rows == 0


def test_poe2_dual_registrar_uses_anchored_coverage_without_player_mask():
    registrar = build_poe2_dual_first_frame_registrar(
        type(
            "Config",
            (),
            {
                "first_frame_minimum_confidence": 0.70,
                "first_frame_anchored_score": 0.35,
                "first_frame_anchored_coverage": 0.45,
            },
        )()
    )

    assert registrar.registrar.config.minimum_forward_coverage_when_anchored == 0.45
    assert registrar.registrar.config.player_clear_radius == 0
    assert registrar.registrar.config.top_exclusion_rows == 0


def test_dual_shape_registration_uses_walkable_boundary_not_blocked_storage_layer():
    walkable = np.zeros((40, 40), dtype=bool)
    walkable[10:30, 8:32] = True
    reference = TerrainReference(
        walkable_mask=walkable,
        wall_layer=np.full((40, 40), 255, dtype=np.uint8),
        explored_map=np.full((40, 40), 255, dtype=np.uint8),
        width=40,
        height=40,
        metadata={"instance_id": "Area:1"},
    )

    terrain = _reference_match_terrain(reference)

    assert terrain[0, 0] == 0
    assert terrain[20, 20] == 60
    assert int(np.count_nonzero(terrain == 235)) < int(np.count_nonzero(reference.wall_layer))


def test_marker_adapter_keeps_candidates_unassigned_and_limits_noise():
    observation = ObservationFrame(
        captured_at_ms=100,
        candidates=(
            ObservationCandidate((10, 12), 0.65, evidence={"area": 4}),
            ObservationCandidate((70, 62), 0.95, evidence={"area": 12}),
            ObservationCandidate((90, 90), 0.20, evidence={"area": 2}),
        ),
        source="test",
    )

    candidates = marker_candidates_from_observation(observation)

    assert [candidate.candidate_id for candidate in candidates] == [
        "observation-1",
        "observation-0",
    ]
    assert all(not candidate.color_features.get("identity") for candidate in candidates)


def test_saturated_marker_detector_finds_two_compact_colored_players_and_filters_wall():
    image = np.zeros((80, 100, 3), dtype=np.uint8)
    image[20:26, 15:21] = (0, 140, 255)  # compact orange BGR marker
    image[52:58, 70:76] = (255, 120, 0)  # compact blue BGR marker
    image[2:18, 2:30] = (0, 180, 255)  # large saturated wall/label noise

    observation = detect_saturated_marker_observation(image, captured_at_ms=123)
    candidates = marker_candidates_from_observation(observation)

    assert len(candidates) == 2
    positions = {candidate.local_position for candidate in candidates}
    assert any(abs(x - 17.5) <= 1.0 and abs(y - 22.5) <= 1.0 for x, y in positions)
    assert any(abs(x - 72.5) <= 1.0 and abs(y - 54.5) <= 1.0 for x, y in positions)
    assert all(candidate.color_features["detector"] == "saturated_components" for candidate in candidates)


def test_color_profiles_round_trip_and_limit_detection_to_configured_hues():
    image = np.zeros((80, 100, 3), dtype=np.uint8)
    image[20:26, 15:21] = (0, 140, 255)  # orange
    image[52:58, 70:76] = (255, 120, 0)  # blue
    orange = MarkerColorProfile(
        name="orange-player",
        hue_min=5,
        hue_max=25,
        saturation_min=120,
        value_min=120,
    )
    blue = MarkerColorProfile(
        name="blue-player",
        hue_min=90,
        hue_max=125,
        saturation_min=120,
        value_min=80,
    )

    payload = orange.to_dict()
    assert MarkerColorProfile.from_dict(payload) == orange
    observation = detect_saturated_marker_observation(
        image, captured_at_ms=123, profiles=(orange, blue)
    )
    candidates = marker_candidates_from_observation(observation)

    assert len(candidates) == 2
    assert {candidate.color_features["profile"] for candidate in candidates} == {
        "orange-player",
        "blue-player",
    }


def test_dual_joint_initialization_reports_relative_geometry():
    frame, reference, anchors, candidates, registration = _fixture()
    registrar = DualFirstFrameRegistrar(
        _FakeRegistrar(expected_primary=candidates[0].local_position, registration=registration)
    )

    result = registrar.register(
        frame,
        reference=reference,
        anchors=anchors,
        candidates=candidates,
    )

    assert result.status == "accepted"
    diagnostics = result.diagnostics
    assert diagnostics["joint_initialization"]["pair_distance_error"] <= 1e-6
    assert diagnostics["joint_initialization"]["scale"] > 0


def test_dual_first_frame_uses_midpoint_geometry_when_pair_baseline_is_too_small():
    frame, reference, _anchors, _candidates, registration = _fixture()
    close_first = (40.0, 45.0)
    close_second = (48.0, 52.0)
    close_candidates = (
        PlayerMarkerCandidate("marker-p1", close_first, confidence=0.95),
        PlayerMarkerCandidate("marker-p2", close_second, confidence=0.92),
    )
    # Keep the fixture's trusted registration, but make the memory pair agree
    # with the close screen pair so the test isolates the degenerate-baseline
    # routing decision.
    close_anchors = {
        "p1": PositionAnchor(
            transform_local_point(
                frame.wall_mask.shape,
                close_first,
                angle=registration.transform.angle_degrees,
                reflect_horizontal=registration.transform.reflect_horizontal,
                scale=registration.transform.scale,
                translation=registration.transform.translation,
            ),
            "Area:1",
            100,
            "memory",
        ),
        "p2": PositionAnchor(
            transform_local_point(
                frame.wall_mask.shape,
                close_second,
                angle=registration.transform.angle_degrees,
                reflect_horizontal=registration.transform.reflect_horizontal,
                scale=registration.transform.scale,
                translation=registration.transform.translation,
            ),
            "Area:1",
            100,
            "memory",
        ),
    }
    registrar_impl = _RecordingRegistrar(registration)
    registrar = DualFirstFrameRegistrar(registrar_impl)

    result = registrar.register(
        frame,
        reference=reference,
        anchors=close_anchors,
        candidates=close_candidates,
    )

    assert result.status == "accepted"
    assert result.diagnostics["joint_initialization"]["pair_mode"] == "midpoint_geometry"
    assert any(
        call[0] == (44.0, 48.5)
        and call[1]
        == (
            (close_anchors["p1"].position[0] + close_anchors["p2"].position[0]) / 2.0,
            (close_anchors["p1"].position[1] + close_anchors["p2"].position[1]) / 2.0,
        )
        for call in registrar_impl.calls
    )


def test_midpoint_geometry_uses_wall_search_instead_of_direct_pair_fit(monkeypatch):
    frame, reference, _anchors, _candidates, registration = _fixture()
    close_first = (40.0, 45.0)
    close_second = (48.0, 52.0)
    close_anchors = {
        "p1": PositionAnchor((100.0, 100.0), "Area:1", 100, "memory"),
        "p2": PositionAnchor((108.0, 108.0), "Area:1", 100, "memory"),
    }
    joint = _joint_similarity_estimates(
        close_first,
        close_second,
        close_anchors["p1"].position,
        close_anchors["p2"].position,
    )[0]
    seen = {}

    def fail_direct(*_args, **_kwargs):
        raise AssertionError("midpoint geometry must not accept a direct pair fit")

    def fake_shape_register(self, _frame, *, config, **_kwargs):
        seen["angles"] = config.coarse_angles
        seen["reflections"] = config.coarse_reflections
        seen["scales"] = config.coarse_scales
        return registration

    monkeypatch.setattr(DualFirstFrameRegistrar, "_direct_joint_registration", fail_direct)
    monkeypatch.setattr(DualFirstFrameRegistrar, "_midpoint_shape_registration", fake_shape_register)

    registrar = DualFirstFrameRegistrar(AnchoredAbsoluteRegistrar())
    result = registrar._register_near_midpoint_geometry(
        frame,
        primary_frame=frame,
        reference=reference,
        first_anchor=close_anchors["p1"],
        second_anchor=close_anchors["p2"],
        joint=joint,
    )

    assert result is registration
    assert seen["angles"] == AnchoredAbsoluteRegistrar().config.coarse_angles
    assert seen["reflections"] == (False, True)


def test_dual_memory_provider_converts_both_samples_with_one_orientation():
    class _Source:
        def read_many(self, expected_instance_id):
            assert expected_instance_id == "Area:1"
            return (
                Poe2EntityPositionSample(
                    "p1", "Metadata/Characters/A", (100.0, 200.0, 0.0),
                    (10.0, 20.0), "2026-09-25T00:00:00+00:00", "Area:1", 1,
                ),
                Poe2EntityPositionSample(
                    "p2", "Metadata/Characters/B", (110.0, 210.0, 0.0),
                    (11.0, 21.0), "2026-09-25T00:00:00+00:00", "Area:1", 2,
                ),
            )

    provider = Poe2DualMemoryAnchorProvider(
        _Source(), TerrainOrientation(rotation=90), (100, 80), clock_ms=lambda: 42
    )
    anchors = provider.read_once("Area:1")

    assert provider.read_count == 1
    assert anchors["p1"].position == (79.0, 10.0)
    assert anchors["p2"].position == (78.0, 11.0)
    assert all(anchor.source == "poe2_dual_memory" for anchor in anchors.values())


def test_dual_first_frame_experiment_wires_observation_to_registrar():
    frame, reference, anchors, candidates, registration = _fixture()
    observation = ObservationFrame(
        captured_at_ms=100,
        candidates=tuple(
            ObservationCandidate(
                tuple(int(value) for value in candidate.local_position),
                candidate.confidence,
            )
            for candidate in candidates
        ),
    )

    class _AnchorProvider:
        def read_once(self, expected_instance_id):
            return anchors

    experiment = DualFirstFrameExperiment(
        _AnchorProvider(),
        DualFirstFrameRegistrar(
            _FakeRegistrar(expected_primary=candidates[0].local_position, registration=registration)
        ),
    )

    result = experiment.register(
        frame,
        reference=reference,
        anchors=experiment.read_anchors("Area:1"),
        observation=observation,
    )

    assert result.accepted


def test_dual_first_frame_experiment_bounds_registration_candidates():
    frame, reference, anchors, _candidates, _registration = _fixture()
    observation = ObservationFrame(
        captured_at_ms=100,
        candidates=tuple(
            ObservationCandidate((10 + index * 3, 12 + index), 0.9 - index * 0.01)
            for index in range(6)
        ),
    )
    seen = []

    class _Registrar:
        def register(self, frame, *, reference, anchors, candidates):
            del frame, reference, anchors
            seen.append(tuple(candidates))
            return "registration"

    experiment = DualFirstFrameExperiment(
        type("_Provider", (), {"read_once": lambda _self, _instance: anchors})(),
        _Registrar(),
    )

    assert experiment.register(
        frame,
        reference=reference,
        anchors=experiment.read_anchors("Area:1"),
        observation=observation,
    ) == "registration"
    assert len(seen) == 1
    assert len(seen[0]) == 4
