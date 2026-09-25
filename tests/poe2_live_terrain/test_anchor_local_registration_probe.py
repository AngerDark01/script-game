from __future__ import annotations

import json

import cv2
import numpy as np
import pytest

from tools.debug.poe2_anchor_local_registration_probe import (
    AnchorLocalProbeConfig,
    AnchorLocalProbeInput,
    crop_terrain_around_anchor,
    load_anchor_probe_input,
    match_anchor_local,
    prepare_local_feature,
    save_probe_diagnostics,
)
from tools.debug.poe2_live_terrain_localization_probe import transform_feature


def _write_sample(tmp_path, *, position_instance: str = "Area:hash"):
    sample = tmp_path / "sample"
    sample.mkdir()
    terrain = np.zeros((80, 100, 3), dtype=np.uint8)
    terrain[20:60, 10:90] = 60
    cv2.rectangle(terrain, (10, 20), (89, 59), (235, 235, 235), 1)
    feature = np.zeros((20, 20), dtype=np.uint8)
    cv2.line(feature, (0, 6), (18, 6), 255, 1)
    for name, image in {
        "raw.png": np.zeros((20, 20, 3), dtype=np.uint8),
        "feature.png": feature,
        "wall_mask.png": feature,
        "terrain.png": terrain,
    }.items():
        assert cv2.imwrite(str(sample / name), image)
    manifest = {
        "terrain": {
            "status": "available",
            "instance_id": "Area:hash",
            "width": 100,
            "height": 80,
        },
        "player_position": {
            "status": "available",
            "area_instance": position_instance,
            "captured_at": "2026-09-22T00:00:00+00:00",
            "world": [100.0, 200.0, 0.0],
            "grid": [40.0, 35.0],
        },
        "monitor_config": {
            "binding": {"player_marker_position": [10, 10]},
        },
    }
    (sample / "sample.json").write_text(
        json.dumps(manifest, ensure_ascii=False),
        encoding="utf-8",
    )
    return sample


def test_load_anchor_probe_input_requires_matching_instances(tmp_path):
    valid = load_anchor_probe_input(_write_sample(tmp_path))

    assert valid.anchor_grid == (40.0, 35.0)
    assert valid.local_player == (10.0, 10.0)
    assert valid.terrain.shape == (80, 100, 3)

    mismatch_root = tmp_path / "mismatch"
    mismatch_root.mkdir()
    mismatch = _write_sample(mismatch_root, position_instance="Area:other")
    with pytest.raises(ValueError, match="same area instance"):
        load_anchor_probe_input(mismatch)


def test_load_anchor_probe_input_uses_oriented_terrain_grid_and_rejects_bad_marker(tmp_path):
    sample = _write_sample(tmp_path)
    manifest_path = sample / "sample.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["player_position"]["terrain_grid"] = [55.0, 42.0]
    manifest["monitor_config"]["binding"]["player_marker_position"] = [float("nan"), 10]
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(ValueError, match="local player position must be finite"):
        load_anchor_probe_input(sample)

    manifest["monitor_config"]["binding"]["player_marker_position"] = [10, 10]
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    loaded = load_anchor_probe_input(sample)

    assert loaded.anchor_grid == (55.0, 42.0)


def test_crop_and_feature_preparation_are_bounded_and_non_mutating():
    terrain = np.zeros((40, 50, 3), dtype=np.uint8)
    crop, bounds = crop_terrain_around_anchor(terrain, (4.0, 5.0), 12)

    assert bounds == (0, 0, 17, 18)
    assert crop.shape == (18, 17, 3)

    feature = np.full((30, 40), 255, dtype=np.uint8)
    prepared = prepare_local_feature(
        feature,
        (20.0, 15.0),
        top_exclusion_rows=5,
        player_clear_radius=3,
    )

    assert np.all(feature == 255)
    assert np.count_nonzero(prepared[:5]) == 0
    assert prepared[15, 20] == 0
    assert prepared[15, 10] == 255


def test_anchor_local_match_recovers_known_transform(tmp_path):
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
    terrain = np.full((360, 420, 3), 60, dtype=np.uint8)
    top_left = (173, 121)
    height, width = transformed.mask.shape
    target = terrain[top_left[1] : top_left[1] + height, top_left[0] : top_left[0] + width]
    target[transformed.mask > 0] = 235
    expected_player = (
        top_left[0] + transformed.player_position[0],
        top_left[1] + transformed.player_position[1],
    )
    probe_input = AnchorLocalProbeInput(
        sample_root=None,
        manifest={},
        terrain=terrain,
        feature=feature,
        local_player=player,
        anchor_grid=(expected_player[0] + 2.0, expected_player[1] - 1.0),
    )
    config = AnchorLocalProbeConfig(
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

    result = match_anchor_local(probe_input, config)

    assert result.status == "anchored_candidate"
    assert result.best is not None
    assert result.best.registration.angle == 45.0
    assert result.best.registration.reflect_horizontal is True
    assert result.best.registration.scale == pytest.approx(1.2)
    assert result.best.global_player_position == pytest.approx(expected_player, abs=3.0)
    assert result.best.anchor_error <= 4.0

    output = save_probe_diagnostics(
        probe_input,
        result,
        tmp_path / "output",
        config=config,
    )
    report = json.loads((output / "report.json").read_text(encoding="utf-8"))

    assert report["status"] == "anchored_candidate"
    assert report["best"]["global_player_position"] == pytest.approx(expected_player, abs=3.0)
    assert (output / "local_terrain.png").is_file()
    assert (output / "prepared_feature.png").is_file()
    assert (output / "best_overlay.png").is_file()


def test_anchor_local_match_reports_symmetric_directions_as_ambiguous():
    feature = np.zeros((64, 64), dtype=np.uint8)
    cv2.rectangle(feature, (8, 8), (55, 55), 255, 2)
    player = (31.5, 31.5)
    terrain = np.full((240, 240, 3), 60, dtype=np.uint8)
    top_left = (91, 87)
    target = terrain[top_left[1] : top_left[1] + 64, top_left[0] : top_left[0] + 64]
    target[feature > 0] = 235
    expected_player = (top_left[0] + player[0], top_left[1] + player[1])
    probe_input = AnchorLocalProbeInput(
        sample_root=None,
        manifest={},
        terrain=terrain,
        feature=feature,
        local_player=player,
        anchor_grid=expected_player,
    )
    config = AnchorLocalProbeConfig(
        crop_radius=110,
        refine_crop_radius=95,
        top_exclusion_rows=0,
        player_clear_radius=0,
        max_anchor_error=20.0,
        coarse_angles=(0.0, 90.0, 180.0, 270.0),
        coarse_reflections=(False,),
        coarse_scales=(1.0,),
        refine_angle_radius=0.0,
        refine_scale_radius=0.0,
        refine_seed_count=4,
        refine_seed_margin=1.0,
        minimum_score=0.50,
        minimum_forward_coverage=0.50,
    )

    result = match_anchor_local(probe_input, config)

    assert result.status == "ambiguous"
    assert len({candidate.basin_angle for candidate in result.candidates}) >= 2
