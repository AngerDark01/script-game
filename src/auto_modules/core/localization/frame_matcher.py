from __future__ import annotations

import cv2


def normalized_wall_close_kernel_size(kernel_size) -> int:
    """Return a positive odd morphology kernel size."""
    size = max(1, int(kernel_size))
    if size % 2 == 0:
        size += 1
    return size


def wall_close_kernel(kernel_size):
    """Create the wall-template close kernel used before template matching."""
    size = normalized_wall_close_kernel_size(kernel_size)
    return cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (size, size))


def standardize_wall_template(wall_mask_scaled, kernel_size):
    """Apply the same wall thickness normalization used by navigation matching."""
    if int(kernel_size) <= 1:
        return wall_mask_scaled
    return cv2.morphologyEx(wall_mask_scaled, cv2.MORPH_CLOSE, wall_close_kernel(kernel_size))


def scaled_template_size(mask_shape, draw_scale) -> tuple[int, int]:
    """Return scaled template size as (height, width)."""
    h_raw, w_raw = mask_shape[:2]
    return int(h_raw * float(draw_scale)), int(w_raw * float(draw_scale))


def scale_wall_template(wall_mask, draw_scale, close_kernel_size):
    """Resize a 1x minimap wall mask to map scale and normalize wall thickness."""
    h_scaled, w_scaled = scaled_template_size(wall_mask.shape, draw_scale)
    wall_mask_scaled = cv2.resize(
        wall_mask,
        (w_scaled, h_scaled),
        interpolation=cv2.INTER_NEAREST,
    )
    return standardize_wall_template(wall_mask_scaled, close_kernel_size)


def select_template_search_area(
    *,
    wall_layer,
    current_pos,
    canvas_size,
    local_search_radius,
    full_map_localization,
    wall_mask_shape,
    draw_scale,
):
    """Select the full-map or local template-match search area."""
    search_area = wall_layer
    top_left_offset = (0, 0)

    if full_map_localization:
        return search_area, top_left_offset

    cx, cy = int(current_pos[0]), int(current_pos[1])
    radius = int(local_search_radius)

    x1 = max(0, cx - radius)
    y1 = max(0, cy - radius)
    x2 = min(int(canvas_size), cx + radius)
    y2 = min(int(canvas_size), cy + radius)

    search_area = wall_layer[y1:y2, x1:x2]
    top_left_offset = (x1, y1)

    h_scaled, w_scaled = scaled_template_size(wall_mask_shape, draw_scale)
    if search_area.shape[0] < h_scaled or search_area.shape[1] < w_scaled:
        return wall_layer, (0, 0)

    return search_area, top_left_offset
