from __future__ import annotations

import cv2
import numpy as np

from tools.debug.poe2_live_terrain_localization_probe import (
    ProbeConfig,
    clean_feature_mask,
    local_walkable_region,
    search_candidates,
    transform_feature,
)


def test_clean_feature_mask_removes_compact_icons_and_keeps_map_geometry():
    feature = np.zeros((120, 120), dtype=np.uint8)
    cv2.line(feature, (0, 18), (86, 18), 255, 2)
    cv2.line(feature, (86, 18), (86, 92), 255, 2)
    cv2.circle(feature, (32, 72), 7, 255, 2)
    cv2.line(feature, (101, 98), (108, 112), 255, 2)

    cleaned, components = clean_feature_mask(
        feature,
        player_position=(60.0, 60.0),
        player_clear_radius=8,
        min_component_area=12,
        min_component_span=20,
    )

    assert cleaned[18, 12] == 255
    assert cleaned[72, 32] == 0
    assert cleaned[104, 104] == 0
    assert any(item["kept"] for item in components)
    assert sum(bool(item["kept"]) for item in components) == 1


def test_local_walkable_region_uses_player_side_of_boundary():
    feature = np.zeros((80, 100), dtype=np.uint8)
    cv2.rectangle(feature, (20, 14), (78, 68), 255, 2)

    region = local_walkable_region(feature, (50.0, 40.0))

    assert region[40, 50] == 255
    assert region[5, 5] == 0
    assert region[14, 50] == 0


def test_chamfer_search_recovers_rotation_reflection_scale_and_position():
    feature = np.zeros((72, 88), dtype=np.uint8)
    cv2.line(feature, (3, 8), (70, 8), 255, 2)
    cv2.line(feature, (70, 8), (70, 48), 255, 2)
    cv2.line(feature, (70, 48), (42, 48), 255, 2)
    cv2.line(feature, (42, 48), (42, 67), 255, 2)
    player = (30.0, 34.0)
    expected = transform_feature(
        feature,
        player,
        angle=45.0,
        reflect_horizontal=True,
        scale=1.2,
    )
    terrain = np.zeros((360, 420), dtype=np.uint8)
    top_left = (173, 121)
    height, width = expected.mask.shape
    terrain[top_left[1] : top_left[1] + height, top_left[0] : top_left[0] + width] = expected.mask

    config = ProbeConfig(
        angles=(0.0, 45.0, 90.0),
        reflect_horizontal=(False, True),
        scales=(0.8, 1.0, 1.2, 1.4),
        coarse_factor=0.5,
        coarse_per_variant=1,
        coarse_keep=8,
        refine_angle_offsets=(0.0,),
        refine_scale_offsets=(0.0,),
        refine_radius=16,
        match_tolerance=2.0,
        reverse_tolerance=2.0,
        min_template_edge_pixels=40,
        max_results=3,
        min_spatial_separation=24.0,
    )

    candidates = search_candidates(feature, terrain, player_position=player, config=config)

    assert candidates
    best = candidates[0]
    assert best.angle == 45.0
    assert best.reflect_horizontal is True
    assert best.scale == 1.2
    assert abs(best.top_left[0] - top_left[0]) <= 2
    assert abs(best.top_left[1] - top_left[1]) <= 2
    expected_player = (
        top_left[0] + expected.player_position[0],
        top_left[1] + expected.player_position[1],
    )
    assert np.linalg.norm(np.subtract(best.player_position, expected_player)) <= 3.0
    assert best.score >= 0.90


def test_walkable_evidence_breaks_identical_edge_tie():
    feature = np.zeros((60, 70), dtype=np.uint8)
    cv2.rectangle(feature, (5, 5), (64, 54), 255, 2)
    player = (32.0, 30.0)
    terrain = np.zeros((220, 320), dtype=np.uint8)
    wrong_top_left = (24, 30)
    right_top_left = (194, 122)
    for x, y in (wrong_top_left, right_top_left):
        terrain[y : y + feature.shape[0], x : x + feature.shape[1]] |= feature
    walkable = np.zeros_like(terrain)
    cv2.rectangle(
        walkable,
        (right_top_left[0] + 8, right_top_left[1] + 8),
        (right_top_left[0] + 61, right_top_left[1] + 51),
        255,
        thickness=-1,
    )
    config = ProbeConfig(
        angles=(0.0,),
        reflect_horizontal=(False,),
        scales=(1.0,),
        coarse_factor=0.5,
        coarse_per_variant=2,
        coarse_keep=2,
        refine_angle_offsets=(0.0,),
        refine_scale_offsets=(0.0,),
        refine_radius=12,
        min_template_edge_pixels=40,
        max_results=2,
        min_spatial_separation=60.0,
    )

    candidates = search_candidates(
        feature,
        terrain,
        player_position=player,
        terrain_walkable=walkable,
        config=config,
    )

    assert len(candidates) == 2
    assert candidates[0].player_on_walkable is True
    assert candidates[0].walkable_coverage > candidates[1].walkable_coverage
    assert np.linalg.norm(np.subtract(candidates[0].top_left, right_top_left)) <= 2.0


def test_player_hint_is_applied_before_coarse_top_k_truncation():
    feature = np.zeros((28, 32), dtype=np.uint8)
    cv2.line(feature, (2, 3), (28, 3), 255, 2)
    cv2.line(feature, (28, 3), (28, 23), 255, 2)
    player = (12.0, 14.0)
    terrain = np.zeros((500, 500), dtype=np.uint8)
    placements = [(20 + column * 90, 20 + row * 90) for row in range(5) for column in range(5)]
    for x, y in placements:
        terrain[y : y + feature.shape[0], x : x + feature.shape[1]] |= feature
    target = placements[-1]
    hint = (target[0] + player[0], target[1] + player[1])
    config = ProbeConfig(
        angles=(0.0,),
        reflect_horizontal=(False,),
        scales=(1.0,),
        coarse_factor=1.0,
        coarse_per_variant=25,
        coarse_keep=16,
        refine_angle_offsets=(0.0,),
        refine_scale_offsets=(0.0,),
        refine_radius=4,
        min_template_edge_pixels=20,
        max_results=16,
        min_spatial_separation=0.0,
        player_position_hint=hint,
        player_position_radius=6.0,
    )

    candidates = search_candidates(feature, terrain, player_position=player, config=config)

    assert candidates
    assert np.linalg.norm(np.subtract(candidates[0].top_left, target)) <= 1.0
    assert np.linalg.norm(np.subtract(candidates[0].player_position, hint)) <= 1.0
