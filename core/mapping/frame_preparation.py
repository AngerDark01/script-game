from __future__ import annotations

import cv2
import numpy as np


def standardize_wall_thickness(mask, wall_close_kernel_size):
    """Apply the stitching wall-thickness close operation."""
    size = max(1, int(wall_close_kernel_size))
    if size % 2 == 0:
        size += 1
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (size, size))
    return cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)


def prepare_scaled_frame_masks(save_mask, fog_mask, *, draw_scale, wall_close_kernel_size):
    """Scale save/fog masks to map resolution and normalize the wall mask."""
    h, w = save_mask.shape
    h_scaled = int(h * float(draw_scale))
    w_scaled = int(w * float(draw_scale))

    save_mask_scaled = cv2.resize(save_mask, (w_scaled, h_scaled), interpolation=cv2.INTER_NEAREST)
    fog_mask_scaled = cv2.resize(fog_mask, (w_scaled, h_scaled), interpolation=cv2.INTER_NEAREST)
    save_mask_scaled = standardize_wall_thickness(save_mask_scaled, wall_close_kernel_size)

    return {
        "save_mask_scaled": save_mask_scaled,
        "fog_mask_scaled": fog_mask_scaled,
        "h_scaled": h_scaled,
        "w_scaled": w_scaled,
    }


def scaled_player_pos(px, py, draw_scale) -> tuple[int, int]:
    """Scale the player local minimap position to map resolution."""
    return int(px * float(draw_scale)), int(py * float(draw_scale))


def is_too_similar(roi_wall, save_mask, *, min_overlap=100, iou_threshold=0.95) -> bool:
    """Return whether two wall masks are already nearly identical in the overlap region."""
    overlap = (roi_wall > 127) | (save_mask > 127)
    if np.sum(overlap) < int(min_overlap):
        return False

    intersection = np.sum((roi_wall > 127) & (save_mask > 127))
    union = np.sum(overlap)
    iou = intersection / union
    return bool(iou > float(iou_threshold))


def bounds_in_canvas(x1, y1, x2, y2, canvas_size) -> bool:
    """Return whether a rectangle is fully inside the map canvas."""
    return (
        0 <= x1 < int(canvas_size)
        and 0 <= y1 < int(canvas_size)
        and 0 < x2 <= int(canvas_size)
        and 0 < y2 <= int(canvas_size)
    )
