from __future__ import annotations

import numpy as np


def merge_frame_weighted(stitcher, save_mask, fog_mask, h, w, px, py, *, force: bool = False) -> bool:
    """Merge one scaled frame into a MapStitcher canvas.

    Returns True when pixels were merged and False when the frame was skipped
    because it was out of bounds or redundant.
    """
    cur_x, cur_y = int(stitcher.current_x), int(stitcher.current_y)

    x1 = cur_x - px
    y1 = cur_y - py
    x2 = x1 + w
    y2 = y1 + h

    c_x1 = max(0, x1)
    c_y1 = max(0, y1)
    c_x2 = min(stitcher.canvas_size, x2)
    c_y2 = min(stitcher.canvas_size, y2)
    if c_x1 >= c_x2 or c_y1 >= c_y2:
        return False

    src_x1 = c_x1 - x1
    src_y1 = c_y1 - y1
    src_x2 = src_x1 + (c_x2 - c_x1)
    src_y2 = src_y1 + (c_y2 - c_y1)

    save_mask_clipped = save_mask[src_y1:src_y2, src_x1:src_x2]
    fog_mask_clipped = fog_mask[src_y1:src_y2, src_x1:src_x2]

    roi_weight = stitcher.weight_layer[c_y1:c_y2, c_x1:c_x2]
    roi_wall = stitcher.wall_layer[c_y1:c_y2, c_x1:c_x2]
    roi_fog = stitcher.fog_layer[c_y1:c_y2, c_x1:c_x2]
    roi_explored = stitcher.explored_map[c_y1:c_y2, c_x1:c_x2]

    if stitcher._is_too_similar(roi_wall, save_mask_clipped) and not force:
        print("[防止重复] 内容太相似，跳过本次绘制")
        stitcher.stats["redundant_prevented"] = stitcher.stats.get("redundant_prevented", 0) + 1
        return False

    new_wall_mask = save_mask_clipped > 127
    roi_weight[new_wall_mask] += stitcher.weight_add
    np.clip(roi_weight, 0, stitcher.weight_cap, out=roi_weight)

    if force:
        roi_weight[new_wall_mask] = stitcher.weight_cap
        visible_wall_mask = new_wall_mask
    else:
        visible_wall_mask = roi_weight > 1.0

    roi_wall[visible_wall_mask] = 255

    fog_visible_mask = fog_mask_clipped > 127
    fog_pixels = int(np.count_nonzero(fog_visible_mask))
    if fog_pixels >= stitcher.precise_visibility_min_pixels:
        roi_fog[fog_visible_mask] = 255

    if stitcher.use_precise_visibility_mask and fog_pixels >= stitcher.precise_visibility_min_pixels:
        view_mask = np.zeros_like(roi_explored, dtype=np.uint8)
        view_mask[fog_visible_mask] = 255
    else:
        view_mask = np.full_like(roi_explored, 255)

    view_mask[new_wall_mask] = 255
    np.maximum(roi_explored, view_mask, out=roi_explored)
    stitcher.canvas[c_y1:c_y2, c_x1:c_x2] = roi_wall
    return True
