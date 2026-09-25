import cv2
import numpy as np
import pytest

from auto_modules.core.localization import LocalizationResult
from auto_modules.features.poe2.live_terrain.experimental.hybrid_localization.absolute_registrar import (
    AnchoredCandidate,
    AnchoredAbsoluteRegistrar,
    AnchoredRegistrationConfig,
    _deduplicate_anchored_candidates,
    _prioritize_memory_anchor,
    _result_status,
    _refine_seeds,
    prepare_local_feature,
    reference_boundary_layer,
)


def test_default_top_exclusion_removes_dynamic_top_overlay_rows():
    assert AnchoredRegistrationConfig().top_exclusion_rows == 40
from auto_modules.features.poe2.live_terrain.experimental.hybrid_localization.models import (
    AbsoluteRegistration,
    HybridFrame,
    PositionAnchor,
    SimilarityTransform2D,
)
from auto_modules.features.poe2.live_terrain.experimental.hybrid_localization.similarity_search import (
    SearchCandidate,
    transform_feature,
)
from auto_modules.features.poe2.live_terrain.terrain_reference import TerrainReference


AREA = "Map:A1"


def test_reference_boundary_layer_excludes_filled_blocked_interiors():
    walkable = np.zeros((11, 13), dtype=bool)
    walkable[3:8, 4:10] = True
    reference = TerrainReference(
        walkable_mask=walkable,
        wall_layer=np.where(walkable, 0, 255).astype(np.uint8),
        explored_map=np.full(walkable.shape, 255, dtype=np.uint8),
        width=walkable.shape[1],
        height=walkable.shape[0],
        metadata={"instance_id": AREA},
    )

    boundary = reference_boundary_layer(reference)

    assert boundary.dtype == np.uint8
    assert boundary[0, 0] == 0
    assert boundary[5, 6] == 0
    assert boundary[2, 4] == 255
    assert boundary[3, 4] == 255


def build_case():
    feature = np.zeros((72, 88), dtype=np.uint8)
    cv2.line(feature, (3, 8), (70, 8), 255, 2)
    cv2.line(feature, (70, 8), (70, 48), 255, 2)
    cv2.line(feature, (70, 48), (42, 48), 255, 2)
    cv2.line(feature, (42, 48), (42, 67), 255, 2)
    player = (30.0, 34.0)
    transformed = transform_feature(
        feature,
        player,
        angle=45.0,
        reflect_horizontal=True,
        scale=1.2,
    )
    terrain = np.zeros((360, 420), dtype=np.uint8)
    terrain[20:340, 20:400] = 60
    top_left = (173, 121)
    height, width = transformed.mask.shape
    patch = terrain[top_left[1] : top_left[1] + height, top_left[0] : top_left[0] + width]
    patch[transformed.mask > 0] = 235
    expected_player = (
        top_left[0] + transformed.player_position[0],
        top_left[1] + transformed.player_position[1],
    )
    reference = TerrainReference(
        walkable_mask=(terrain >= 20) & (terrain < 180),
        wall_layer=np.where(terrain >= 180, 255, 0).astype(np.uint8),
        explored_map=np.where(terrain > 0, 255, 0).astype(np.uint8),
        width=terrain.shape[1],
        height=terrain.shape[0],
        metadata={"instance_id": AREA},
    )
    frame = HybridFrame(1, 1000, feature, player)
    anchor = PositionAnchor(
        (expected_player[0] + 2.0, expected_player[1] - 1.0),
        AREA,
        1000,
        "memory",
    )
    return frame, reference, anchor, expected_player


def test_default_capture_window_matches_200px_minimap_calibration():
    config = AnchoredRegistrationConfig()

    assert config.crop_radius == 150
    assert config.refine_crop_radius == 110
    assert config.capture_reference_size == 200
    assert config.similarity_score_weights == (0.55, 0.25, 0.15, 0.05)


def test_real_capture_window_scales_from_actual_frame_size():
    frame = HybridFrame(
        frame_id=1,
        captured_at_ms=1000,
        wall_mask=np.zeros((320, 320), dtype=np.uint8),
        local_player=(160.0, 160.0),
        diagnostics={"capture_size": 320},
    )
    registrar = AnchoredAbsoluteRegistrar()

    config = registrar._config_for_frame(frame, registrar.config)

    assert config.crop_radius == 240
    assert config.refine_crop_radius == 176
    assert config.top_exclusion_rows == 64
    assert config.player_clear_radius == 22


def test_prepare_local_feature_removes_compact_detached_noise() -> None:
    feature = np.zeros((120, 120), dtype=np.uint8)
    cv2.line(feature, (0, 24), (90, 24), 255, 2)
    cv2.line(feature, (90, 24), (90, 95), 255, 2)
    cv2.circle(feature, (28, 86), 7, 255, 2)
    cv2.line(feature, (103, 101), (109, 112), 255, 2)

    prepared = prepare_local_feature(
        feature,
        (60.0, 60.0),
        top_exclusion_rows=0,
        player_clear_radius=8,
    )

    assert prepared[24, 12] == 255
    assert prepared[86, 28] == 0
    assert prepared[106, 106] == 0


def test_offline_frame_keeps_explicit_crop_window():
    frame = HybridFrame(
        frame_id=1,
        captured_at_ms=1000,
        wall_mask=np.zeros((64, 64), dtype=np.uint8),
        local_player=(32.0, 32.0),
    )
    base = AnchoredRegistrationConfig(crop_radius=130, refine_crop_radius=95)
    registrar = AnchoredAbsoluteRegistrar(base)

    config = registrar._config_for_frame(frame, base)

    assert config.crop_radius == 130
    assert config.refine_crop_radius == 95


def test_registrar_recovers_known_similarity_transform():
    frame, reference, anchor, expected_player = build_case()
    registrar = AnchoredAbsoluteRegistrar(
        AnchoredRegistrationConfig(
            crop_radius=130,
            refine_crop_radius=110,
            top_exclusion_rows=0,
            player_clear_radius=0,
            max_anchor_error=30.0,
            coarse_angles=(0.0, 45.0, 90.0),
            coarse_reflections=(False, True),
            coarse_scales=(0.8, 1.0, 1.2, 1.4),
            refine_angle_radius=0.0,
            refine_scale_radius=0.0,
            minimum_score=0.70,
            minimum_forward_coverage=0.70,
        )
    )

    result = registrar.register(frame, reference=reference, anchor=anchor)

    assert result is not None
    assert result.result.position == pytest.approx(expected_player, abs=3.0)
    assert result.transform.angle_degrees == 45.0
    assert result.transform.reflect_horizontal is True
    assert result.transform.scale == pytest.approx(1.2)
    assert result.anchor_error <= 4.0
    assert result.area_instance == AREA


def test_prior_locks_angle_reflection_and_scale():
    frame, reference, anchor, _ = build_case()
    prior = AbsoluteRegistration(
        result=LocalizationResult(anchor.position, 0.9, source="anchored_absolute"),
        transform=SimilarityTransform2D(45.0, True, 1.2, (173.0, 121.0)),
        anchor_error=0.0,
        area_instance=AREA,
    )
    registrar = AnchoredAbsoluteRegistrar(
        AnchoredRegistrationConfig(
            crop_radius=130,
            refine_crop_radius=110,
            top_exclusion_rows=0,
            player_clear_radius=0,
            max_anchor_error=30.0,
            minimum_score=0.65,
            minimum_forward_coverage=0.65,
        )
    )

    result = registrar.register(frame, reference=reference, anchor=anchor, prior=prior)

    assert result is not None
    assert result.transform.angle_degrees == prior.transform.angle_degrees
    assert result.transform.reflect_horizontal is prior.transform.reflect_horizontal
    assert result.transform.scale == prior.transform.scale
    assert result.diagnostics["search_mode"] == "translation_only"
    assert result.diagnostics["coarse_variant_count"] == 1


def test_recovery_falls_back_to_full_orientation_when_prior_basin_fails():
    frame, reference, anchor, expected_player = build_case()
    prior = AbsoluteRegistration(
        result=LocalizationResult(anchor.position, 0.9, source="anchored_absolute"),
        transform=SimilarityTransform2D(0.0, False, 1.0, (0.0, 0.0)),
        anchor_error=0.0,
        area_instance=AREA,
    )
    registrar = AnchoredAbsoluteRegistrar(
        AnchoredRegistrationConfig(
            crop_radius=130,
            refine_crop_radius=110,
            top_exclusion_rows=0,
            player_clear_radius=0,
            max_anchor_error=30.0,
            coarse_angles=(0.0, 45.0, 90.0),
            coarse_reflections=(False, True),
            coarse_scales=(0.8, 1.0, 1.2, 1.4),
            refine_angle_radius=0.0,
            refine_scale_radius=0.0,
            minimum_score=0.70,
            minimum_forward_coverage=0.70,
        )
    )

    result = registrar.register(frame, reference=reference, anchor=anchor, prior=prior)

    assert result is not None
    assert result.result.position == pytest.approx(expected_player, abs=3.0)
    assert result.transform.angle_degrees == 45.0
    assert result.diagnostics["search_mode"] == "full_similarity_recovery"
    assert result.diagnostics["attempt_count"] == 2


def test_registrar_rejects_cross_instance_prior_without_searching():
    frame, reference, anchor, _ = build_case()
    prior = AbsoluteRegistration(
        result=LocalizationResult(anchor.position, 0.9, source="anchored_absolute"),
        transform=SimilarityTransform2D(45.0, True, 1.2, (173.0, 121.0)),
        anchor_error=0.0,
        area_instance="Map:OLD",
    )

    assert AnchoredAbsoluteRegistrar().register(
        frame,
        reference=reference,
        anchor=anchor,
        prior=prior,
    ) is None


def test_rejected_registration_exposes_probe_diagnostics():
    frame, reference, anchor, _ = build_case()
    registrar = AnchoredAbsoluteRegistrar(
        AnchoredRegistrationConfig(
            crop_radius=130,
            refine_crop_radius=110,
            top_exclusion_rows=0,
            player_clear_radius=0,
            max_anchor_error=30.0,
            coarse_angles=(45.0,),
            coarse_reflections=(True,),
            coarse_scales=(1.2,),
            refine_angle_radius=0.0,
            refine_scale_radius=0.0,
            minimum_score=1.01,
            minimum_margin=0.0,
        )
    )

    result = registrar.register(frame, reference=reference, anchor=anchor)

    assert result is None
    assert registrar.last_diagnostics["status"] == "rejected"
    assert registrar.last_diagnostics["reason"] == "best candidate score is below the anchored threshold"
    assert registrar.last_diagnostics["candidate_count"] >= 1
    assert registrar.last_diagnostics["best_score"] < 1.01
    assert registrar.last_diagnostics["best_angle"] == 45.0
    assert registrar.last_diagnostics["best_reflection"] is True
    assert registrar.last_diagnostics["best_scale"] == pytest.approx(1.2)


def test_close_walkable_anchor_allows_narrow_forward_coverage_tolerance():
    registration = SearchCandidate(
        angle=219.0,
        reflect_horizontal=True,
        scale=0.81,
        top_left=(12, 17),
        player_position=(126.0, 130.0),
        mean_distance=3.4,
        forward_coverage=0.633,
        reverse_coverage=0.36,
        walkable_coverage=0.66,
        player_on_walkable=True,
        score=0.55,
        edge_pixels=800,
    )
    candidate = AnchoredCandidate(
        registration=registration,
        global_player_position=(344.0, 406.0),
        anchor_error=3.0,
        anchored_score=0.65,
        basin_angle=225.0,
        basin_reflection=True,
    )

    status, reason = _result_status(
        (candidate,),
        AnchoredRegistrationConfig(),
    )

    assert status == "anchored_candidate"
    assert reason == "single-frame geometry is consistent with close memory anchor"


def test_close_walkable_anchor_uses_explicit_poe2_relaxed_quality_gates():
    registration = SearchCandidate(
        angle=225.0,
        reflect_horizontal=True,
        scale=0.77,
        top_left=(12, 17),
        player_position=(126.0, 130.0),
        mean_distance=3.4,
        forward_coverage=0.511,
        reverse_coverage=0.36,
        walkable_coverage=0.66,
        player_on_walkable=True,
        score=0.396,
        edge_pixels=800,
    )
    candidate = AnchoredCandidate(
        registration=registration,
        global_player_position=(303.25, 695.78),
        anchor_error=0.325,
        anchored_score=0.786,
        basin_angle=225.0,
        basin_reflection=True,
        basin_scale=0.77,
    )

    status, reason = _result_status(
        (candidate,),
        AnchoredRegistrationConfig(
            minimum_confidence=0.75,
            minimum_score=0.50,
            minimum_score_when_anchored=0.35,
            minimum_forward_coverage=0.65,
            minimum_forward_coverage_when_anchored=0.50,
        ),
    )

    assert status == "anchored_candidate"
    assert reason == "single-frame geometry is consistent with close memory anchor"


def test_memory_anchor_breaks_close_visual_score_tie():
    def candidate(error, score, angle):
        registration = SearchCandidate(
            angle=angle,
            reflect_horizontal=True,
            scale=1.0,
            top_left=(0, 0),
            player_position=(10.0, 10.0),
            mean_distance=1.0,
            forward_coverage=0.9,
            reverse_coverage=0.4,
            walkable_coverage=0.8,
            player_on_walkable=True,
            score=score,
            edge_pixels=100,
        )
        return AnchoredCandidate(
            registration=registration,
            global_player_position=(error, 0.0),
            anchor_error=error,
            anchored_score=score,
            basin_angle=angle,
            basin_reflection=True,
        )

    config = AnchoredRegistrationConfig(minimum_margin=0.03)
    visual_best = candidate(7.0, 0.70, 215.0)
    anchor_best = candidate(2.0, 0.60, 182.0)
    ordered = _prioritize_memory_anchor((visual_best, anchor_best), config)

    assert ordered[0] is anchor_best
    status, _reason = _result_status(ordered, config)
    assert status == "anchored_candidate"


def test_adjacent_refinements_from_same_search_basin_are_not_ambiguous():
    def candidate(angle: float, anchored_score: float, anchor_error: float):
        registration = SearchCandidate(
            angle=angle,
            reflect_horizontal=True,
            scale=0.77,
            top_left=(0, 0),
            player_position=(10.0, 10.0),
            mean_distance=2.0,
            forward_coverage=0.65,
            reverse_coverage=0.30,
            walkable_coverage=0.29,
            player_on_walkable=True,
            score=0.51,
            edge_pixels=100,
        )
        return AnchoredCandidate(
            registration=registration,
            global_player_position=(100.0, 100.0),
            anchor_error=anchor_error,
            anchored_score=anchored_score,
            basin_angle=225.0,
            basin_reflection=True,
            basin_scale=0.75,
        )

    status, _reason = _result_status(
        (
            candidate(221.0, 0.811, 1.95),
            candidate(219.0, 0.809, 2.64),
        ),
        AnchoredRegistrationConfig(minimum_confidence=0.80),
    )

    assert status == "anchored_candidate"


def test_production_confidence_gate_rejects_sub_eighty_candidate():
    registration = SearchCandidate(
        angle=219.0,
        reflect_horizontal=True,
        scale=0.75,
        top_left=(0, 0),
        player_position=(10.0, 10.0),
        mean_distance=2.0,
        forward_coverage=0.80,
        reverse_coverage=0.30,
        walkable_coverage=0.30,
        player_on_walkable=True,
        score=0.56,
        edge_pixels=100,
    )
    candidate = AnchoredCandidate(
        registration=registration,
        global_player_position=(100.0, 100.0),
        anchor_error=3.0,
        anchored_score=0.79,
        basin_angle=225.0,
        basin_reflection=True,
    )

    status, reason = _result_status(
        (candidate,),
        AnchoredRegistrationConfig(minimum_confidence=0.80),
    )

    assert status == "rejected"
    assert reason == "best candidate confidence is below threshold"


def test_forward_coverage_tolerance_does_not_accept_far_or_blocked_candidate():
    registration = SearchCandidate(
        angle=219.0,
        reflect_horizontal=True,
        scale=0.81,
        top_left=(12, 17),
        player_position=(126.0, 130.0),
        mean_distance=3.4,
        forward_coverage=0.633,
        reverse_coverage=0.36,
        walkable_coverage=0.66,
        player_on_walkable=False,
        score=0.55,
        edge_pixels=800,
    )
    candidate = AnchoredCandidate(
        registration=registration,
        global_player_position=(344.0, 406.0),
        anchor_error=3.0,
        anchored_score=0.65,
        basin_angle=225.0,
        basin_reflection=True,
    )

    status, reason = _result_status(
        (candidate,),
        AnchoredRegistrationConfig(),
    )

    assert status == "rejected"
    assert reason == "best candidate forward coverage is below threshold"


def test_deduplicate_keeps_orientation_ambiguity_but_removes_exact_refined_duplicate():
    def candidate(angle, reflected, scale, x):
        registration = SearchCandidate(
            angle=angle,
            reflect_horizontal=reflected,
            scale=scale,
            top_left=(0, 0),
            player_position=(10.0, 10.0),
            mean_distance=1.0,
            forward_coverage=0.8,
            reverse_coverage=0.4,
            walkable_coverage=0.7,
            player_on_walkable=True,
            score=0.6,
            edge_pixels=100,
        )
        return AnchoredCandidate(
            registration=registration,
            global_player_position=(x, 10.0),
            anchor_error=1.0,
            anchored_score=0.7,
            basin_angle=angle,
            basin_reflection=reflected,
        )

    candidates = (
        candidate(219.0, True, 0.81, 344.0),
        candidate(219.0, True, 0.810001, 344.4),
        candidate(39.0, True, 0.81, 344.0),
    )

    unique = _deduplicate_anchored_candidates(candidates)

    assert len(unique) == 2
    assert {item.registration.angle for item in unique} == {219.0, 39.0}


def test_refine_seeds_preserve_separated_scale_modes_in_the_best_orientation():
    def candidate(angle, reflected, scale, anchored_score):
        registration = SearchCandidate(
            angle=angle,
            reflect_horizontal=reflected,
            scale=scale,
            top_left=(0, 0),
            player_position=(10.0, 10.0),
            mean_distance=1.0,
            forward_coverage=0.8,
            reverse_coverage=0.2,
            walkable_coverage=0.5,
            player_on_walkable=True,
            score=anchored_score,
            edge_pixels=100,
        )
        return AnchoredCandidate(
            registration=registration,
            global_player_position=(10.0, 10.0),
            anchor_error=1.0,
            anchored_score=anchored_score,
            basin_angle=angle,
            basin_reflection=reflected,
        )

    candidates = (
        candidate(225.0, True, 1.15, 0.69),
        candidate(225.0, True, 1.05, 0.68),
        candidate(0.0, False, 1.25, 0.67),
        candidate(315.0, False, 1.05, 0.65),
        candidate(90.0, True, 1.55, 0.64),
        candidate(225.0, True, 0.85, 0.62),
    )
    config = AnchoredRegistrationConfig(
        refine_seed_count=8,
        refine_orientation_seed_count=4,
        refine_seed_margin=0.10,
        refine_scale_radius=0.16,
    )

    selected = _refine_seeds(candidates, config)

    best_orientation_scales = [
        item.registration.scale
        for item in selected
        if item.registration.angle == 225.0
        and item.registration.reflect_horizontal is True
    ]
    assert best_orientation_scales == [1.15, 0.85]
