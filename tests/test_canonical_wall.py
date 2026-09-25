import cv2
import numpy as np
import pytest

from auto_modules.core.localization.canonical_wall import (
    canonical_boundary_from_walkable,
    canonical_wall_mask,
)


def test_canonical_wall_mask_is_binary_and_does_not_mutate_input():
    source = np.zeros((12, 12), dtype=np.uint8)
    source[4:8, 4:8] = 200
    before = source.copy()

    result = canonical_wall_mask(source)

    assert result.dtype == np.uint8
    assert set(np.unique(result)).issubset({0, 255})
    assert np.array_equal(source, before)


def test_canonical_wall_mask_removes_small_components():
    source = np.zeros((16, 16), dtype=np.uint8)
    source[2:8, 2:8] = 255
    source[13, 13] = 255

    result = canonical_wall_mask(source, min_component_area=4)

    assert result[4, 4] == 255
    assert result[13, 13] == 0


def test_boundary_respects_explored_mask():
    walkable = np.ones((10, 10), dtype=np.uint8)
    explored = np.zeros_like(walkable)
    explored[2:8, 2:8] = 1

    result = canonical_boundary_from_walkable(walkable, explored)

    assert result.dtype == np.uint8
    assert not np.any(result[0:2])
    assert not np.any(result[:, 0:2])


def test_boundary_rejects_mismatched_explored_shape():
    with pytest.raises(ValueError, match="explored shape"):
        canonical_boundary_from_walkable(np.ones((4, 4)), np.ones((3, 3)))
