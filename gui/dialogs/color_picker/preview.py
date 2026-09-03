"""Preview mask construction for the color picker dialog."""

from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np


@dataclass(frozen=True)
class WallPreviewResult:
    """Wall HSV preview mask and diagnostics."""

    mask: object
    mask_before_morph: object
    hsv: object
    min_hsv: object
    max_hsv: object
    white_pixels: int
    total_pixels: int
    white_ratio: float
    pixels_after_close: int
    pixels_after_close_diff: int


def build_wall_preview(image, wall_hsv_range) -> WallPreviewResult | None:
    """Build the wall binary preview mask from a processed BGR screenshot."""
    if wall_hsv_range is None:
        return None

    min_hsv, max_hsv = wall_hsv_range
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    wall_mask = cv2.inRange(hsv, min_hsv, max_hsv)

    white_pixels = int(np.count_nonzero(wall_mask))
    total_pixels = int(wall_mask.size)
    white_ratio = white_pixels / total_pixels if total_pixels > 0 else 0

    kernel = np.ones((3, 3), np.uint8)
    wall_mask_before_morph = wall_mask.copy()
    wall_mask_after_close = wall_mask.copy()
    wall_mask = cv2.morphologyEx(wall_mask, cv2.MORPH_CLOSE, kernel)
    pixels_after_close = int(np.count_nonzero(wall_mask))
    pixels_after_close_diff = int(np.count_nonzero(wall_mask_after_close) - pixels_after_close)

    return WallPreviewResult(
        mask=wall_mask,
        mask_before_morph=wall_mask_before_morph,
        hsv=hsv,
        min_hsv=min_hsv,
        max_hsv=max_hsv,
        white_pixels=white_pixels,
        total_pixels=total_pixels,
        white_ratio=white_ratio,
        pixels_after_close=pixels_after_close,
        pixels_after_close_diff=pixels_after_close_diff,
    )
