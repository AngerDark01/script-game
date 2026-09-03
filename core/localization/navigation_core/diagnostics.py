from __future__ import annotations

import time

import cv2


def log_template_match_failure(
    nav_core,
    *,
    max_val,
    required_conf,
    full_map_localization,
    force_global,
    force_global_reason,
    wall_mask,
    wall_mask_scaled,
    search_area,
    wall_feature_count,
) -> None:
    """Throttle and print detailed localization template-match failure diagnostics."""
    now_ms = int(time.monotonic() * 1000)
    if (
        nav_core._last_template_fail_log_ms
        and now_ms - nav_core._last_template_fail_log_ms < 1500
    ):
        return
    nav_core._last_template_fail_log_ms = now_ms
    print(
        "Localization template match failed: "
        f"conf={float(max_val):.3f}, required={float(required_conf):.3f}, "
        f"full_map={bool(full_map_localization)}, forced={bool(force_global)}, "
        f"reason={force_global_reason or 'normal'}, "
        f"draw_scale={float(nav_core.draw_scale):.3f}, "
        f"map_draw_scale={float(getattr(nav_core, 'map_draw_scale', nav_core.draw_scale)):.3f}, "
        f"wall_features={int(wall_feature_count)}, "
        f"raw_mask={tuple(int(v) for v in wall_mask.shape)}, "
        f"scaled_mask={tuple(int(v) for v in wall_mask_scaled.shape)}, "
        f"scaled_features={int(cv2.countNonZero(wall_mask_scaled))}, "
        f"search={tuple(int(v) for v in search_area.shape)}, "
        f"close_kernel={int(getattr(nav_core, 'wall_match_close_kernel_size', 3))}"
    )
