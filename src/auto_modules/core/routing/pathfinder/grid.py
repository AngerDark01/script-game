from __future__ import annotations

import cv2
import numpy as np


def build_obstacle_map(
    wall_map,
    grid_w: int,
    grid_h: int,
    *,
    downsample_factor: int,
    safety_margin: int = 0,
    wall_shrink_iterations: int = 0,
    explored_map=None,
):
    """Build the downsampled obstacle grid used by A*."""
    source = wall_map
    if source.dtype != np.uint8:
        source = source.astype(np.uint8)

    _, binary_source = cv2.threshold(source, 50, 255, cv2.THRESH_BINARY)
    if int(wall_shrink_iterations) > 0:
        thin_kernel = cv2.getStructuringElement(cv2.MORPH_CROSS, (3, 3))
        binary_source = cv2.erode(
            binary_source,
            thin_kernel,
            iterations=int(wall_shrink_iterations),
        )

    small_map = cv2.resize(binary_source, (grid_w, grid_h), interpolation=cv2.INTER_AREA)
    _, binary_map = cv2.threshold(small_map, 50, 255, cv2.THRESH_BINARY)

    if explored_map is not None:
        binary_map = apply_explored_obstacles(
            binary_map,
            explored_map,
            grid_w=grid_w,
            grid_h=grid_h,
        )

    return apply_safety_margin(
        binary_map,
        safety_margin=int(safety_margin),
        downsample_factor=int(downsample_factor),
    )


def apply_explored_obstacles(binary_map, explored_map, *, grid_w: int, grid_h: int):
    """Treat unexplored cells as obstacles in an existing obstacle grid."""
    known_source = explored_map
    if known_source.dtype != np.uint8:
        known_source = known_source.astype(np.uint8)
    _, known_source = cv2.threshold(known_source, 1, 255, cv2.THRESH_BINARY)
    known_small = cv2.resize(known_source, (grid_w, grid_h), interpolation=cv2.INTER_AREA)
    _, known_map = cv2.threshold(known_small, 1, 255, cv2.THRESH_BINARY)
    unknown_obstacle = np.where(known_map > 0, 0, 255).astype(np.uint8)
    return np.maximum(binary_map, unknown_obstacle)


def apply_safety_margin(binary_map, *, safety_margin: int, downsample_factor: int):
    """Dilate obstacles by a map-space safety margin converted to grid cells."""
    if int(safety_margin) <= 0:
        return binary_map

    grid_margin = int(round(int(safety_margin) / max(1, int(downsample_factor))))
    if grid_margin <= 0:
        return binary_map

    kernel_size = grid_margin * 2 + 1
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (kernel_size, kernel_size))
    return cv2.dilate(binary_map, kernel)


def clear_start_area(
    obstacle_map,
    start_grid,
    *,
    start_clear_radius: int,
    downsample_factor: int,
):
    """Forgive local wall noise around the live player position."""
    radius = int(round(int(start_clear_radius) / max(1, int(downsample_factor))))
    if radius <= 0:
        return obstacle_map

    cleared = obstacle_map.copy()
    h, w = cleared.shape
    cx, cy = int(start_grid[0]), int(start_grid[1])
    x1 = max(0, cx - radius)
    y1 = max(0, cy - radius)
    x2 = min(w, cx + radius + 1)
    y2 = min(h, cy + radius + 1)
    if x1 >= x2 or y1 >= y2:
        return cleared

    local = cleared[y1:y2, x1:x2]
    mask = np.zeros_like(local, dtype=np.uint8)
    cv2.circle(mask, (cx - x1, cy - y1), radius, 255, -1)
    local[mask > 0] = 0
    return cleared
