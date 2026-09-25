import numpy as np

from auto_modules.features.poe2.live_terrain.experimental.hybrid_localization.models import SimilarityTransform2D
from auto_modules.features.poe2.live_terrain.experimental.multiframe_localization.shape_registration import (
    _reference_geometry,
    score_shape,
)


def test_shape_score_accepts_same_wall_shape_with_translation():
    wall = np.zeros((12, 12), dtype=np.uint8)
    wall[3:9, 3] = 255
    reference = np.zeros((32, 32), dtype=np.uint8)
    reference[8:14, 13] = 255
    observed = np.full_like(wall, 255)
    result = score_shape(
        wall_mask=wall,
        observed_mask=observed,
        reference_boundary=reference,
        transform=SimilarityTransform2D(0, False, 1, (10, 5)),
        threshold=1.5,
    )
    assert result.forward_coverage > 0.8
    assert result.reverse_coverage > 0.8
    assert result.usable_points == 6


def test_empty_wall_shape_is_not_a_match():
    result = score_shape(
        wall_mask=np.zeros((4, 4), dtype=np.uint8),
        observed_mask=np.ones((4, 4), dtype=np.uint8),
        reference_boundary=np.ones((8, 8), dtype=np.uint8),
        transform=SimilarityTransform2D(0, False, 1, (0, 0)),
    )
    assert result.usable_points == 0
    assert result.score == 0.0


def test_reverse_coverage_counts_only_reference_walls_inside_observed_view():
    wall = np.zeros((12, 12), dtype=np.uint8)
    wall[3:9, 3] = 255
    observed = np.full_like(wall, 255)
    reference = np.zeros((40, 40), dtype=np.uint8)
    reference[8:14, 13] = 255
    reference[8:14, 18] = 255
    result = score_shape(
        wall_mask=wall,
        observed_mask=observed,
        reference_boundary=reference,
        transform=SimilarityTransform2D(0, False, 1, (10, 5)),
        threshold=1.5,
    )
    assert result.forward_coverage > 0.8
    assert 0.4 <= result.reverse_coverage <= 0.6
    assert result.reverse_error > 0


def test_huber_trim_reduces_outlier_error_without_hiding_raw_coverage():
    wall = np.zeros((20, 20), dtype=np.uint8)
    wall[4:16, 4] = 255
    wall[18, 18] = 255
    observed = np.full_like(wall, 255)
    reference = np.zeros((40, 40), dtype=np.uint8)
    reference[9:21, 14] = 255
    transform = SimilarityTransform2D(0, False, 1, (10, 5))

    untrimmed = score_shape(
        wall_mask=wall,
        observed_mask=observed,
        reference_boundary=reference,
        transform=transform,
        trim_fraction=0.0,
    )
    trimmed = score_shape(
        wall_mask=wall,
        observed_mask=observed,
        reference_boundary=reference,
        transform=transform,
        trim_fraction=0.1,
    )

    assert trimmed.forward_error < untrimmed.forward_error
    assert trimmed.forward_coverage == untrimmed.forward_coverage


def test_aligned_line_has_low_tangent_error():
    wall = np.zeros((16, 16), dtype=np.uint8)
    wall[3:13, 7] = 255
    reference = np.zeros((32, 32), dtype=np.uint8)
    reference[8:18, 17] = 255

    result = score_shape(
        wall_mask=wall,
        observed_mask=np.full_like(wall, 255),
        reference_boundary=reference,
        transform=SimilarityTransform2D(0, False, 1, (10, 5)),
    )

    assert result.tangent_error < 0.2


def test_reference_geometry_is_cached_for_the_same_reference_array():
    reference = np.eye(16, dtype=np.uint8) * 255

    first = _reference_geometry(reference)
    second = _reference_geometry(reference)

    assert first is second
