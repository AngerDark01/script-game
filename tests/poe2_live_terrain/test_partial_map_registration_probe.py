from __future__ import annotations

import json

import cv2
import numpy as np
import pytest

from tools.debug.poe2_partial_map_registration_probe import (
    HoughConfig,
    RegistrationCandidate,
    RegistrationConfig,
    binary_mask,
    decide_result,
    generate_overlap_candidates,
    load_probe_input,
    normalize_shape,
    project_point,
    register_partial_map,
    save_registration_diagnostics,
    score_candidate,
    warp_candidate,
)


def test_registration_config_rejects_invalid_trim_fraction():
    with pytest.raises(ValueError, match="trim_fraction"):
        RegistrationConfig(trim_fraction=1.0)


def test_binary_mask_selects_bright_wall_boundary_in_rendered_map():
    rendered = np.zeros((80, 100), dtype=np.uint8)
    cv2.rectangle(rendered, (10, 10), (90, 70), 60, -1)
    cv2.rectangle(rendered, (10, 10), (90, 70), 235, 2)

    mask = binary_mask(rendered)

    assert mask[40, 50] == 0
    assert mask[10, 50] == 255


def test_candidate_serializes_transform_fields():
    candidate = RegistrationCandidate(
        center=(12.5, 18.0),
        angle=45.0,
        scale=0.35,
        reflected=True,
        hough_votes=(20, 30, 40),
    )

    assert candidate.as_dict()["center"] == [12.5, 18.0]
    assert candidate.as_dict()["reflected"] is True


def test_normalize_shape_is_stable_across_wall_thickness():
    thin = np.zeros((120, 160), dtype=np.uint8)
    thick = np.zeros_like(thin)
    points = np.array([[10, 95], [45, 30], [105, 30], [145, 85]], np.int32)
    cv2.polylines(thin, [points], False, 255, 2)
    cv2.polylines(thick, [points], False, 255, 11)

    thin_shape = normalize_shape(thin)
    thick_shape = normalize_shape(thick)
    distance = cv2.distanceTransform(
        np.where(thin_shape > 0, 0, 255).astype(np.uint8),
        cv2.DIST_L2,
        3,
    )

    assert np.mean(distance[thick_shape > 0] <= 2.0) >= 0.95
    ratio = np.count_nonzero(thick_shape) / np.count_nonzero(thin_shape)
    assert 0.75 <= ratio <= 1.25


def test_normalize_shape_preserves_rotated_one_pixel_fragments():
    original = normalize_shape(_asymmetric_shape(2))
    rotated = _place_shape(original, (460, 360), (286.0, 194.0), 35.0, 0.8)

    normalized_again = normalize_shape(rotated)
    distance = cv2.distanceTransform(
        np.where(rotated > 0, 0, 255).astype(np.uint8),
        cv2.DIST_L2,
        3,
    )

    assert np.mean(distance[normalized_again > 0] <= 1.0) >= 0.98
    assert np.count_nonzero(normalized_again) / np.count_nonzero(rotated) >= 0.95


def test_project_point_applies_rotation_scale_and_translation():
    result = project_point(
        (30.0, 20.0),
        local_center=(20.0, 20.0),
        global_center=(100.0, 80.0),
        angle=90.0,
        scale=2.0,
        reflected=False,
    )

    assert np.allclose(result, (100.0, 100.0), atol=1e-5)


def test_warp_candidate_preserves_thin_line_topology_when_downscaling():
    local = normalize_shape(_asymmetric_shape(9))
    candidate = RegistrationCandidate((300.0, 240.0), 35.0, 0.12, False, (0, 0, 0))

    projected = warp_candidate(local, (480, 600), candidate)

    expected_line_length = cv2.countNonZero(local) * candidate.scale
    assert cv2.countNonZero(projected) >= expected_line_length * 0.50


def _asymmetric_shape(thickness: int = 2) -> np.ndarray:
    shape = np.zeros((100, 120), dtype=np.uint8)
    cv2.line(shape, (12, 82), (28, 18), 255, thickness)
    cv2.line(shape, (28, 18), (91, 18), 255, thickness)
    cv2.line(shape, (91, 18), (106, 62), 255, thickness)
    cv2.circle(shape, (73, 61), 12, 255, thickness)
    cv2.line(shape, (18, 72), (54, 87), 255, thickness)
    return shape


def _place_shape(
    shape: np.ndarray,
    size: tuple[int, int],
    center: tuple[float, float],
    angle: float,
    scale: float,
) -> np.ndarray:
    local_center = ((shape.shape[1] - 1) / 2.0, (shape.shape[0] - 1) / 2.0)
    matrix = cv2.getRotationMatrix2D(local_center, -angle, scale)
    matrix[0, 2] += center[0] - local_center[0]
    matrix[1, 2] += center[1] - local_center[1]
    return cv2.warpAffine(shape, matrix, size, flags=cv2.INTER_NEAREST)


def test_overlap_search_recovers_continuous_rotation_scale_and_position_with_clutter():
    local = normalize_shape(_asymmetric_shape(9))
    terrain = _place_shape(local, (460, 360), (286.0, 194.0), 35.0, 0.8)
    cv2.line(terrain, (20, 320), (190, 280), 255, 1)
    cv2.rectangle(terrain, (40, 35), (112, 104), 255, 1)

    candidates = generate_overlap_candidates(
        local,
        normalize_shape(terrain),
        config=HoughConfig(
            angle_step=5.0,
            min_scale=0.65,
            max_scale=0.95,
            scale_step=0.02,
            min_distance=16.0,
            position_threshold=5,
            angle_threshold=15,
            scale_threshold=8,
        ),
        reflected=False,
        downsample=0.5,
        max_candidates=16,
    )

    assert any(
        np.hypot(item.center[0] - 286.0, item.center[1] - 194.0) <= 8.0
        and abs(((item.angle - 35.0 + 180.0) % 360.0) - 180.0) <= 3.0
        and abs(item.scale - 0.8) <= 0.06
        for item in candidates
    )


def test_overlap_search_does_not_prefer_collapsed_scale_in_structural_clutter():
    local = normalize_shape(_asymmetric_shape(9))
    terrain = warp_candidate(
        local,
        (360, 460),
        RegistrationCandidate((286.0, 194.0), 35.0, 0.4, False, (0, 0, 0)),
    )
    cv2.line(terrain, (20, 320), (400, 40), 255, 1)
    cv2.rectangle(terrain, (50, 40), (150, 140), 255, 1)

    candidates = generate_overlap_candidates(
        local,
        normalize_shape(terrain),
        config=HoughConfig(
            angle_step=5.0,
            min_scale=0.10,
            max_scale=0.50,
            scale_step=0.05,
            min_distance=16.0,
        ),
        reflected=False,
        downsample=0.5,
        max_candidates=12,
    )

    assert any(
        np.hypot(item.center[0] - 286.0, item.center[1] - 194.0) <= 8.0
        and abs(((item.angle - 35.0 + 180.0) % 360.0) - 180.0) <= 5.0
        and abs(item.scale - 0.4) <= 0.06
        for item in candidates
    )

    result = register_partial_map(
        local,
        terrain,
        config=RegistrationConfig(
            hough=HoughConfig(
                angle_step=5.0,
                min_scale=0.10,
                max_scale=0.50,
                scale_step=0.05,
                min_distance=16.0,
            ),
            candidate_downsample=0.5,
            max_candidates=12,
            minimum_score=0.50,
            minimum_margin=0.0,
        ),
    )
    winner = result.candidates[0]
    assert np.hypot(winner.center[0] - 286.0, winner.center[1] - 194.0) <= 8.0
    assert abs(((winner.angle - 35.0 + 180.0) % 360.0) - 180.0) <= 5.0
    assert abs(winner.scale - 0.4) <= 0.06


def test_trimmed_chamfer_prefers_correct_candidate_with_coarse_block_noise():
    clean_local = normalize_shape(_asymmetric_shape(9))
    noisy_local = clean_local.copy()
    cv2.rectangle(noisy_local, (2, 2), (35, 35), 255, -1)
    terrain = normalize_shape(
        _place_shape(clean_local, (460, 360), (286.0, 194.0), 35.0, 0.8)
    )
    config = RegistrationConfig(trim_fraction=0.20, distance_tolerance=3.0)
    correct = score_candidate(
        noisy_local,
        terrain,
        RegistrationCandidate((286.0, 194.0), 35.0, 0.8, False, (0, 0, 0)),
        config=config,
    )
    wrong = score_candidate(
        noisy_local,
        terrain,
        RegistrationCandidate((220.0, 145.0), 80.0, 0.8, False, (0, 0, 0)),
        config=config,
    )

    assert correct.score > wrong.score
    assert correct.forward_coverage > wrong.forward_coverage


def test_decide_result_accepts_clear_winner():
    winner = RegistrationCandidate((10.0, 10.0), 35.0, 0.8, False, (0, 0, 0), score=0.82)
    runner_up = RegistrationCandidate((40.0, 40.0), 120.0, 0.8, False, (0, 0, 0), score=0.70)

    result = decide_result([runner_up, winner])

    assert result.accepted is True
    assert result.reason == "accepted"
    assert result.candidates[0] == winner


def test_decide_result_rejects_repeated_room_ambiguity():
    first = RegistrationCandidate((10.0, 10.0), 35.0, 0.8, False, (0, 0, 0), score=0.82)
    second = RegistrationCandidate((140.0, 90.0), 35.0, 0.8, False, (0, 0, 0), score=0.81)

    result = decide_result([first, second])

    assert result.accepted is False
    assert result.reason == "ambiguous"


def test_decide_result_reports_no_match():
    result = decide_result([])

    assert result.accepted is False
    assert result.reason == "no_match"


def test_decide_result_ignores_near_duplicate_of_winner_for_margin():
    winner = RegistrationCandidate((100.0, 80.0), 35.0, 0.80, False, (0, 0, 0), score=0.82)
    same_hypothesis = RegistrationCandidate(
        (103.0, 78.0), 37.0, 0.82, False, (0, 0, 0), score=0.81
    )
    other_room = RegistrationCandidate((230.0, 160.0), 35.0, 0.80, False, (0, 0, 0), score=0.70)

    result = decide_result([same_hypothesis, other_room, winner])

    assert result.accepted is True
    assert result.score_margin == pytest.approx(0.12)


def test_register_partial_map_recovers_transform_across_wall_thickness_and_clutter():
    local = _asymmetric_shape(11)
    clean_shape = normalize_shape(_asymmetric_shape(2))
    terrain = _place_shape(clean_shape, (460, 360), (286.0, 194.0), 35.0, 0.8)
    cv2.line(terrain, (20, 320), (190, 280), 255, 2)
    cv2.rectangle(local, (2, 2), (35, 35), 255, -1)
    config = RegistrationConfig(
        hough=HoughConfig(
            angle_step=5.0,
            min_scale=0.65,
            max_scale=0.95,
            scale_step=0.02,
            min_distance=16.0,
        ),
        trim_fraction=0.20,
        candidate_downsample=0.5,
        max_candidates=16,
        minimum_score=0.60,
        minimum_margin=0.03,
    )

    result = register_partial_map(local, terrain, config=config)

    assert result.accepted is True, result.reason
    winner = result.candidates[0]
    assert np.hypot(winner.center[0] - 286.0, winner.center[1] - 194.0) <= 8.0
    assert abs(((winner.angle - 35.0 + 180.0) % 360.0) - 180.0) <= 3.0
    assert abs(winner.scale - 0.8) <= 0.06


def _write_probe_session(directory, *, include_stitched=True, include_terrain=True):
    directory.mkdir()
    image = np.zeros((40, 60), dtype=np.uint8)
    cv2.line(image, (5, 30), (50, 10), 255, 2)
    if include_stitched:
        cv2.imwrite(str(directory / "stitched_map.png"), image)
    if include_terrain:
        cv2.imwrite(str(directory / "terrain.png"), image)
    (directory / "session.json").write_text(
        json.dumps({"map_origin": [120, 80], "current_position": [147, 99]}),
        encoding="utf-8",
    )
    return image


def test_load_probe_input_prefers_session_terrain_and_computes_local_player(tmp_path):
    session = tmp_path / "session"
    _write_probe_session(session)

    loaded = load_probe_input(session)

    assert loaded.terrain_path == (session / "terrain.png").resolve()
    assert loaded.terrain_source == "session"
    assert loaded.local_player == (27.0, 19.0)
    assert len(loaded.stitched_sha256) == 64
    assert len(loaded.terrain_sha256) == 64


def test_load_probe_input_records_explicit_external_terrain(tmp_path):
    session = tmp_path / "session"
    image = _write_probe_session(session, include_terrain=False)
    external = tmp_path / "external-terrain.png"
    cv2.imwrite(str(external), image)

    loaded = load_probe_input(session, external)

    assert loaded.terrain_path == external.resolve()
    assert loaded.terrain_source == "explicit"


def test_load_probe_input_rejects_missing_stitched_map(tmp_path):
    session = tmp_path / "session"
    _write_probe_session(session, include_stitched=False)

    with pytest.raises(FileNotFoundError, match="stitched map"):
        load_probe_input(session)


def test_load_probe_input_does_not_borrow_missing_terrain(tmp_path):
    session = tmp_path / "session"
    _write_probe_session(session, include_terrain=False)
    historical = tmp_path / "historical" / "terrain.png"
    historical.parent.mkdir()
    cv2.imwrite(str(historical), np.full((10, 10), 255, dtype=np.uint8))

    with pytest.raises(FileNotFoundError, match="explicit terrain path"):
        load_probe_input(session)


def test_save_registration_diagnostics_writes_atomic_report_and_overlays(tmp_path):
    session = tmp_path / "session"
    _write_probe_session(session)
    loaded = load_probe_input(session)
    candidate = RegistrationCandidate(
        center=(29.5, 19.5),
        angle=0.0,
        scale=1.0,
        reflected=False,
        hough_votes=(0, 0, 0),
        score=0.90,
        forward_coverage=0.95,
        reverse_coverage=0.92,
        forward_distance=0.3,
        reverse_distance=0.4,
        proposal_score=0.88,
        source="overlap",
    )
    result = decide_result([candidate], minimum_score=0.68)
    output = tmp_path / "result"

    published = save_registration_diagnostics(
        loaded,
        result,
        output,
        config=RegistrationConfig(min_skeleton_pixels=1),
    )

    assert published == output.resolve()
    for filename in (
        "report.json",
        "local_skeleton.png",
        "terrain_skeleton.png",
        "candidate_01_overlay.png",
        "candidates_sheet.png",
    ):
        assert (output / filename).is_file()
    report = json.loads((output / "report.json").read_text(encoding="utf-8"))
    assert report["schema_version"] == 1
    assert report["accepted"] is True
    assert report["input"]["terrain_source"] == "session"
    assert report["candidates"][0]["projected_player"] == pytest.approx([27.0, 19.0])


def test_save_registration_diagnostics_reports_candidates_beyond_render_limit(tmp_path):
    session = tmp_path / "session"
    _write_probe_session(session)
    loaded = load_probe_input(session)
    candidates = tuple(
        RegistrationCandidate(
            center=(29.5 + index, 19.5),
            angle=float(index * 5),
            scale=1.0,
            reflected=False,
            hough_votes=(0, 0, 0),
            score=0.90 - index * 0.01,
        )
        for index in range(8)
    )
    output = tmp_path / "result"

    save_registration_diagnostics(
        loaded,
        decide_result(list(candidates), minimum_margin=0.0),
        output,
        config=RegistrationConfig(min_skeleton_pixels=1),
    )

    report = json.loads((output / "report.json").read_text(encoding="utf-8"))
    assert len(report["candidates"]) == 8
    assert report["rendered_candidate_count"] == 6
    assert "overlay" not in report["candidates"][6]
