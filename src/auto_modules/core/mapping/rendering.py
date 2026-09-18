from __future__ import annotations

import cv2
import numpy as np


def get_cropped_map(stitcher, margin: int = 0):
    """Build the cropped grayscale map display for a MapStitcher."""
    coords = cv2.findNonZero(stitcher.explored_map)
    if coords is None:
        coords = cv2.findNonZero(stitcher.wall_layer)

    if coords is None:
        return np.zeros((100, 100), dtype=np.uint8)

    x, y, w, h = cv2.boundingRect(coords)

    cx, cy = int(stitcher.current_x), int(stitcher.current_y)
    x2 = max(x + w, cx + 1)
    y2 = max(y + h, cy + 1)
    x = min(x, cx)
    y = min(y, cy)
    w = x2 - x
    h = y2 - y

    x = max(0, x - margin)
    y = max(0, y - margin)
    w = min(stitcher.canvas_size - x, w + 2 * margin)
    h = min(stitcher.canvas_size - y, h + 2 * margin)

    roi_wall = stitcher.wall_layer[y : y + h, x : x + w]
    roi_explored = stitcher.explored_map[y : y + h, x : x + w]

    display = np.zeros_like(roi_wall)
    display[roi_explored > 0] = 60
    display[roi_wall > 0] = 255
    return display


def get_enhanced_map(stitcher, margin: int = 500):
    """Build the colored enhanced map display for a MapStitcher."""
    coords = cv2.findNonZero(stitcher.explored_map)
    if coords is None:
        coords = cv2.findNonZero(stitcher.wall_layer)

    if coords is None:
        return np.zeros((100, 100), dtype=np.uint8)

    x, y, w, h = cv2.boundingRect(coords)

    x = max(0, x - margin)
    y = max(0, y - margin)
    w = min(stitcher.canvas_size - x, w + 2 * margin)
    h = min(stitcher.canvas_size - y, h + 2 * margin)

    roi_wall = stitcher.wall_layer[y : y + h, x : x + w]
    roi_explored = stitcher.explored_map[y : y + h, x : x + w]

    display = np.zeros((h, w, 3), dtype=np.uint8)
    display[roi_explored > 0] = (60, 60, 60)
    display[roi_wall > 0] = (235, 235, 235)
    return display, (x, y)
