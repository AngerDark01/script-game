from __future__ import annotations

import cv2
import numpy as np


def derive_navigation_wall_layer(
    wall_layer,
    *,
    erode_iterations: int = 1,
    threshold: int = 50,
) -> np.ndarray:
    """Build a forgiving wall layer for A* without changing localization data."""
    if wall_layer is None:
        raise ValueError("wall_layer is required")

    source = wall_layer
    if source.dtype != np.uint8:
        source = source.astype(np.uint8)

    _, nav_wall = cv2.threshold(source, int(threshold), 255, cv2.THRESH_BINARY)
    iterations = max(0, int(erode_iterations))
    if iterations > 0:
        kernel = cv2.getStructuringElement(cv2.MORPH_CROSS, (3, 3))
        nav_wall = cv2.erode(nav_wall, kernel, iterations=iterations)
    return nav_wall

