from __future__ import annotations

import numpy as np
import pytest

from auto_modules.core.spatial.capture_geometry import (
    CaptureShape,
    build_capture_mask,
)


def test_circle_mask_keeps_pixels_inside_radius_only() -> None:
    mask = build_capture_mask(5, 5, CaptureShape.CIRCLE)

    assert mask.dtype == np.bool_
    assert mask[2, 2]
    assert not mask[0, 0]


def test_square_mask_keeps_every_pixel() -> None:
    mask = build_capture_mask(3, 4, CaptureShape.SQUARE)

    assert mask.shape == (4, 3)
    assert mask.all()


def test_circle_mask_accepts_explicit_radius() -> None:
    mask = build_capture_mask(7, 7, CaptureShape.CIRCLE, radius=2.0)

    assert mask[3, 3]
    assert mask[3, 5]
    assert not mask[0, 0]


@pytest.mark.parametrize(
    "width,height",
    [(0, 4), (4, 0), (-1, 4), (4, -1)],
)
def test_mask_rejects_non_positive_dimensions(width: int, height: int) -> None:
    with pytest.raises(ValueError, match="positive"):
        build_capture_mask(width, height, CaptureShape.SQUARE)


def test_mask_rejects_non_positive_circle_radius() -> None:
    with pytest.raises(ValueError, match="radius"):
        build_capture_mask(5, 5, CaptureShape.CIRCLE, radius=0)
