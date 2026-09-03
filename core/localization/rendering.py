from __future__ import annotations

import cv2
import numpy as np


def render_navigation_map(nav_core):
    """Render and crop the navigation display map for a NavigationCore."""
    h, w = nav_core.wall_layer.shape
    display_img = np.zeros((h, w, 3), dtype=np.uint8)
    mask_combined = np.zeros((h, w), dtype=bool)

    if nav_core.explored_map is not None:
        mask_explored = nav_core.explored_map > 0
        if np.any(mask_explored):
            display_img[mask_explored] = [40, 40, 40]
            mask_combined |= mask_explored

    if nav_core.wall_layer is not None:
        mask_wall = nav_core.wall_layer > 0
        if np.any(mask_wall):
            display_img[mask_wall] = [220, 220, 220]
            mask_combined |= mask_wall
        else:
            print("Warning: wall_layer is empty (all zeros).")

    coords = cv2.findNonZero(mask_combined.astype(np.uint8))
    if coords is None:
        nav_core.crop_offset = (0, 0)
        return display_img

    x_min, y_min, w_box, h_box = cv2.boundingRect(coords)
    margin = 50
    x_min = max(0, x_min - margin)
    y_min = max(0, y_min - margin)
    x_max = min(w, x_min + w_box + 2 * margin)
    y_max = min(h, y_min + h_box + 2 * margin)

    nav_core.crop_offset = (x_min, y_min)
    print(f"Auto-cropping map to: x[{x_min}:{x_max}], y[{y_min}:{y_max}]")
    return display_img[y_min:y_max, x_min:x_max]
