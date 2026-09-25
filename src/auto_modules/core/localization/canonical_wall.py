"""Domain-neutral wall-shape normalization for localization."""

from __future__ import annotations

import cv2
import numpy as np


def canonical_wall_mask(
    value: np.ndarray,
    *,
    close_kernel_size: int = 3,
    open_kernel_size: int = 1,
    min_component_area: int = 0,
) -> np.ndarray:
    """Return a stable single-channel binary representation of wall-like input."""
    array = np.asarray(value)
    if array.size == 0 or array.ndim not in (2, 3):
        raise ValueError("wall input must be a non-empty 2D or 3D array")
    if array.ndim == 3:
        array = cv2.cvtColor(array, cv2.COLOR_BGR2GRAY)
    result = np.where(array > 0, 255, 0).astype(np.uint8)
    close_size = int(close_kernel_size)
    if close_size > 1:
        kernel = cv2.getStructuringElement(
            cv2.MORPH_ELLIPSE, (close_size, close_size)
        )
        result = cv2.morphologyEx(result, cv2.MORPH_CLOSE, kernel)
    open_size = int(open_kernel_size)
    if open_size > 1:
        kernel = cv2.getStructuringElement(
            cv2.MORPH_ELLIPSE, (open_size, open_size)
        )
        result = cv2.morphologyEx(result, cv2.MORPH_OPEN, kernel)
    area = int(min_component_area)
    if area > 0:
        count, labels, stats, _ = cv2.connectedComponentsWithStats(result, 8)
        filtered = np.zeros_like(result)
        for label in range(1, count):
            if int(stats[label, cv2.CC_STAT_AREA]) >= area:
                filtered[labels == label] = 255
        result = filtered
    return result


def canonical_boundary_from_walkable(
    walkable: np.ndarray,
    explored: np.ndarray | None = None,
    *,
    close_kernel_size: int = 3,
) -> np.ndarray:
    """Convert walkable/explored layers into a thin canonical boundary."""
    walk = np.asarray(walkable).astype(bool)
    if walk.ndim != 2 or walk.size == 0:
        raise ValueError("walkable must be a non-empty 2D array")
    known = (
        np.ones_like(walk, dtype=bool)
        if explored is None
        else np.asarray(explored).astype(bool)
    )
    if known.shape != walk.shape:
        raise ValueError("explored shape must match walkable shape")
    mask = np.where(walk & known, 255, 0).astype(np.uint8)
    mask = canonical_wall_mask(mask, close_kernel_size=close_kernel_size)
    padded = np.pad(mask > 0, 1, mode="constant", constant_values=False)
    kernel = np.ones((3, 3), dtype=np.uint8)
    dilated = cv2.dilate(padded.astype(np.uint8), kernel)[1:-1, 1:-1] > 0
    eroded = cv2.erode(padded.astype(np.uint8), kernel)[1:-1, 1:-1] > 0
    return np.where((dilated & ~eroded) & known, 255, 0).astype(np.uint8)


__all__ = ["canonical_boundary_from_walkable", "canonical_wall_mask"]
