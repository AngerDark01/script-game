from __future__ import annotations

import cv2
import numpy as np

from core.localization.frame_matcher import scale_wall_template, select_template_search_area


def localize_frame(nav_core, minimap_img, player_pos=None):
    """Run NavigationCore.localize without exposing the stateful pipeline as public API."""
    if minimap_img is None:
        nav_core._clear_frame_registration(0.0, "no_frame")
        return None, None, 0.0

    if player_pos is None:
        player_pos = nav_core.last_player_local_pos
    if player_pos is None:
        h_img, w_img = minimap_img.shape[:2]
        player_pos = (w_img // 2, h_img // 2)

    masks = nav_core.recognizer.extract_combined(minimap_img, player_pos=player_pos)
    if masks is None:
        nav_core._clear_frame_registration(0.0, "no_mask")
        return None, None, 0.0

    if isinstance(masks, tuple) and len(masks) >= 2:
        wall_mask = masks[1]
        match_mask = masks[0]
    else:
        wall_mask = masks[0]
        match_mask = masks[0]

    nav_core.last_player_local_pos = player_pos
    force_global = bool(nav_core.force_global_relocalization)
    force_global_reason = str(nav_core.force_global_relocalization_reason or "")

    match_feature_count = cv2.countNonZero(match_mask)
    wall_feature_count = cv2.countNonZero(wall_mask)
    if match_feature_count < nav_core.min_match_features or wall_feature_count < nav_core.min_wall_features:
        nav_core.prev_mask = None
        nav_core.prev_wall_mask = None
        nav_core._clear_frame_registration(0.0, "low_features")
        return None, None, 0.0

    if force_global:
        nav_core.force_global_relocalization = False
        nav_core.force_global_relocalization_reason = ""
    full_map_localization = nav_core._is_full_map_localization(force_global)

    if (
        not force_global
        and nav_core.is_localized
        and nav_core.prev_wall_mask is not None
        and nav_core.current_pos is not None
    ):
        shift, qual = nav_core._estimate_displacement(nav_core.prev_wall_mask, wall_mask)
        if shift is not None:
            dx, dy = shift
            shift_dist = np.hypot(dx, dy)

            if qual <= nav_core.f2f_confidence_threshold:
                shift = None
            elif shift_dist > nav_core.f2f_max_shift and qual < 0.75:
                print(
                    f"F2F rejected: shift={shift_dist:.1f}px, conf={qual:.2f}, "
                    "fallback to template match"
                )
                shift = None

        if shift is not None:
            dx_global = dx * nav_core.draw_scale
            dy_global = dy * nav_core.draw_scale

            nav_core.current_pos = (
                nav_core.current_pos[0] - dx_global,
                nav_core.current_pos[1] - dy_global,
            )
            nav_core.last_good_pos = nav_core.current_pos
            nav_core.prev_mask = match_mask
            nav_core.prev_wall_mask = wall_mask
            metadata = {
                "shift": (float(dx), float(dy)),
                "shift_dist": float(shift_dist),
            }
            metadata.update(nav_core._visual_check_position(wall_mask, player_pos, nav_core.current_pos))
            nav_core._set_frame_registration(
                nav_core.current_pos,
                player_pos,
                minimap_img.shape,
                qual,
                "f2f",
                metadata,
            )

            return nav_core.current_pos[0], nav_core.current_pos[1], qual

    search_area, top_left_offset = select_template_search_area(
        wall_layer=nav_core.wall_layer,
        current_pos=nav_core.current_pos,
        canvas_size=nav_core.canvas_size,
        local_search_radius=nav_core.local_search_radius,
        full_map_localization=full_map_localization,
        wall_mask_shape=wall_mask.shape,
        draw_scale=nav_core.draw_scale,
    )

    try:
        if wall_mask is None or search_area is None:
            nav_core._clear_frame_registration(0.0, "invalid_match_input")
            return None, None, 0.0

        wall_mask_scaled = scale_wall_template(
            wall_mask,
            nav_core.draw_scale,
            getattr(nav_core, "wall_match_close_kernel_size", 3),
        )

        if search_area.dtype != np.uint8:
            search_area = search_area.astype(np.uint8)
        if wall_mask_scaled.dtype != np.uint8:
            wall_mask_scaled = wall_mask_scaled.astype(np.uint8)

        h_s, w_s = search_area.shape
        h_t, w_t = wall_mask_scaled.shape
        if h_t > h_s or w_t > w_s:
            nav_core._clear_frame_registration(0.0, "template_larger_than_search")
            return None, None, 0.0

        result = cv2.matchTemplate(search_area, wall_mask_scaled, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, max_loc = cv2.minMaxLoc(result)
        required_conf = nav_core._template_match_required_confidence(full_map=full_map_localization)

        if max_val >= required_conf:
            player_x_scaled = int(player_pos[0] * nav_core.draw_scale)
            player_y_scaled = int(player_pos[1] * nav_core.draw_scale)
            center_x = top_left_offset[0] + max_loc[0] + player_x_scaled
            center_y = top_left_offset[1] + max_loc[1] + player_y_scaled

            if nav_core.last_good_pos is not None:
                jump = np.hypot(center_x - nav_core.last_good_pos[0], center_y - nav_core.last_good_pos[1])
                if jump > nav_core.relocalize_max_jump and max_val < 0.9 and not full_map_localization:
                    print(
                        f"Relocalization rejected: jump={jump:.1f}px, conf={max_val:.2f}, "
                        f"last_good=({nav_core.last_good_pos[0]:.1f}, {nav_core.last_good_pos[1]:.1f})"
                    )
                    nav_core.is_localized = False
                    nav_core.prev_mask = None
                    nav_core.prev_wall_mask = None
                    nav_core._clear_frame_registration(max_val, "jump_rejected")
                    return None, None, max_val

            if not nav_core.is_first_frame_localized:
                if nav_core.drawing_saved_pos is not None:
                    print("--- FIRST FRAME LOCALIZATION DEBUG ---")
                    saved_pos = nav_core.drawing_saved_pos
                    new_pos = (center_x, center_y)
                    dx = new_pos[0] - saved_pos[0]
                    dy = new_pos[1] - saved_pos[1]
                    print(f"Saved Pos (from Drawing): ({saved_pos[0]:.2f}, {saved_pos[1]:.2f})")
                    print(f"New Pos (from Navigating): ({new_pos[0]:.2f}, {new_pos[1]:.2f})")
                    print(f"Difference (dx, dy): ({dx:.2f}, {dy:.2f})")
                    print("------------------------------------")
                nav_core.is_first_frame_localized = True

            nav_core.current_pos = (center_x, center_y)
            nav_core.last_good_pos = nav_core.current_pos
            nav_core.is_localized = True
            nav_core.prev_mask = match_mask
            nav_core.prev_wall_mask = wall_mask
            nav_core._set_frame_registration(
                nav_core.current_pos,
                player_pos,
                minimap_img.shape,
                max_val,
                "template_match",
                {
                    "template_top_left": (
                        int(top_left_offset[0] + max_loc[0]),
                        int(top_left_offset[1] + max_loc[1]),
                    ),
                    "search_offset": (int(top_left_offset[0]), int(top_left_offset[1])),
                    "forced_global": bool(force_global),
                    "forced_reason": force_global_reason,
                },
            )

            return center_x, center_y, max_val

        nav_core._log_template_match_failure(
            max_val=max_val,
            required_conf=required_conf,
            full_map_localization=full_map_localization,
            force_global=force_global,
            force_global_reason=force_global_reason,
            wall_mask=wall_mask,
            wall_mask_scaled=wall_mask_scaled,
            search_area=search_area,
            wall_feature_count=wall_feature_count,
        )
        if nav_core.is_localized:
            print(f"Local search failed (conf={max_val:.2f}). Switching to global search next time.")
            nav_core.is_localized = False
            nav_core.prev_mask = None
            nav_core.prev_wall_mask = None

        nav_core._clear_frame_registration(max_val, "template_match_failed")
        return None, None, max_val

    except Exception as exc:
        print(f"Localization error: {exc}")
        nav_core._clear_frame_registration(0.0, "exception")
        return None, None, 0.0
