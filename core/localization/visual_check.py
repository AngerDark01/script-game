from __future__ import annotations

import time

import cv2
import numpy as np

from core.localization.frame_matcher import scale_wall_template


def visual_check_position(nav_core, wall_mask, player_pos, expected_player_global_pos) -> dict:
    """Check whether the current minimap frame best aligns near the tracked global position."""
    if not nav_core.visual_check_interval_ms:
        return {}
    now_ms = int(time.monotonic() * 1000)
    if (
        nav_core._last_visual_check_ms
        and now_ms - nav_core._last_visual_check_ms < int(nav_core.visual_check_interval_ms)
    ):
        return {}
    nav_core._last_visual_check_ms = now_ms

    try:
        h_raw, w_raw = wall_mask.shape
        h_scaled = int(h_raw * nav_core.draw_scale)
        w_scaled = int(w_raw * nav_core.draw_scale)
        if h_scaled <= 0 or w_scaled <= 0:
            return {"visual_check": "failed", "visual_fail_reason": "invalid_template_size"}

        wall_mask_scaled = scale_wall_template(
            wall_mask,
            nav_core.draw_scale,
            getattr(nav_core, "wall_match_close_kernel_size", 3),
        )
        if wall_mask_scaled.dtype != np.uint8:
            wall_mask_scaled = wall_mask_scaled.astype(np.uint8)

        player_x_scaled = int(player_pos[0] * nav_core.draw_scale)
        player_y_scaled = int(player_pos[1] * nav_core.draw_scale)
        expected_x = float(expected_player_global_pos[0])
        expected_y = float(expected_player_global_pos[1])
        expected_left = int(round(expected_x - player_x_scaled))
        expected_top = int(round(expected_y - player_y_scaled))
        margin = max(0, int(nav_core.visual_check_margin))

        map_h, map_w = nav_core.wall_layer.shape[:2]
        x1 = max(0, expected_left - margin)
        y1 = max(0, expected_top - margin)
        x2 = min(map_w, expected_left + w_scaled + margin)
        y2 = min(map_h, expected_top + h_scaled + margin)
        search_area = nav_core.wall_layer[y1:y2, x1:x2]
        if search_area.shape[0] < h_scaled or search_area.shape[1] < w_scaled:
            return {"visual_check": "failed", "visual_fail_reason": "search_area_too_small"}
        if search_area.dtype != np.uint8:
            search_area = search_area.astype(np.uint8)

        result = cv2.matchTemplate(search_area, wall_mask_scaled, cv2.TM_CCOEFF_NORMED)
        if result.size <= 0:
            return {"visual_check": "failed", "visual_fail_reason": "empty_result"}
        _, max_val, _, max_loc = cv2.minMaxLoc(result)
        best_left = int(x1 + max_loc[0])
        best_top = int(y1 + max_loc[1])
        best_player = (float(best_left + player_x_scaled), float(best_top + player_y_scaled))
        delta = (best_player[0] - expected_x, best_player[1] - expected_y)
        delta_dist = float(np.hypot(delta[0], delta[1]))

        expected_score = None
        expected_rx = expected_left - x1
        expected_ry = expected_top - y1
        if 0 <= expected_rx < result.shape[1] and 0 <= expected_ry < result.shape[0]:
            expected_score = float(result[expected_ry, expected_rx])

        mismatch = (
            float(max_val) >= float(nav_core.visual_check_min_confidence)
            and delta_dist >= float(nav_core.visual_mismatch_threshold)
        )
        return {
            "visual_check": "ok",
            "visual_conf": float(max_val),
            "visual_expected_score": expected_score,
            "visual_player": best_player,
            "visual_delta": (float(delta[0]), float(delta[1])),
            "visual_delta_dist": delta_dist,
            "visual_mismatch": bool(mismatch),
        }
    except Exception as exc:
        return {"visual_check": "failed", "visual_fail_reason": str(exc)}
