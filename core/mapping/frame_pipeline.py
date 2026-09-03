from __future__ import annotations

import time

import cv2
import numpy as np

from core.mapping.frame_preparation import prepare_scaled_frame_masks, scaled_player_pos


def add_frame_to_stitcher(stitcher, img, match_mask, save_mask, fog_mask, raw_gray=None, player_pos=None):
    """Run MapStitcher.add_frame without exposing the state machine as public API."""
    frame_start = time.perf_counter()
    stitcher.stats["total_frames"] += 1
    frame_num = stitcher.stats["total_frames"]

    h, w = save_mask.shape
    if player_pos is None:
        px, py = w // 2, h // 2
    else:
        px, py = player_pos

    if stitcher.keyframe_mask is None:
        stitcher._place_first_frame(save_mask, fog_mask, px, py)
        stitcher.keyframe_mask = match_mask.copy()
        stitcher.keyframe_pos = (stitcher.current_x, stitcher.current_y)
        stitcher.prev_mask = match_mask.copy()
        stitcher.prev_pos = (stitcher.current_x, stitcher.current_y)
        print(f"[帧 {frame_num}] 🔥 系统初始化完成")
        return True

    match_success = False
    match_type = "None"
    current_quality = 0.0

    k_shift, k_qual = stitcher._estimate_displacement(stitcher.keyframe_mask, match_mask)

    anchor_valid = False
    if k_shift is not None and k_qual > stitcher.keyframe_thresh:
        k_dx_raw, k_dy_raw = k_shift
        dx_global_raw = k_dx_raw * stitcher.draw_scale
        dy_global_raw = k_dy_raw * stitcher.draw_scale
        target_x_raw = stitcher.keyframe_pos[0] - dx_global_raw
        target_y_raw = stitcher.keyframe_pos[1] - dy_global_raw
        dist_jump = np.sqrt((target_x_raw - stitcher.current_x) ** 2 + (target_y_raw - stitcher.current_y) ** 2)

        if dist_jump < 100.0 or k_qual > 0.6:
            anchor_valid = True
        else:
            print(f"[帧 {frame_num}] ⚠️ Anchor跳变过大 ({dist_jump:.1f}px, Q:{k_qual:.2f})，拒绝误匹配")

    if anchor_valid:
        k_dx, k_dy = k_shift
        k_dx, k_dy = stitcher._smooth_displacement(k_dx, k_dy, k_qual)

        dx_global = k_dx * stitcher.draw_scale
        dy_global = k_dy * stitcher.draw_scale
        stitcher.current_x = stitcher.keyframe_pos[0] - dx_global
        stitcher.current_y = stitcher.keyframe_pos[1] - dy_global

        match_success = True
        match_type = "Anchor"
        current_quality = k_qual
    else:
        p_shift, p_qual = stitcher._estimate_displacement(stitcher.prev_mask, match_mask)

        if p_shift is not None and p_qual > stitcher.conf_thresh:
            p_dx, p_dy = p_shift
            p_dx, p_dy = stitcher._smooth_displacement(p_dx, p_dy, p_qual)

            p_dist = np.sqrt(p_dx**2 + p_dy**2)
            if p_dist > 50.0:
                match_success = False
                stitcher.stats["failed_matches"] += 1
                print(f"[帧 {frame_num}] ⚠️ F2F位移过大 ({p_dist:.1f}px)，忽略跳变 (Q:{p_qual:.2f})")
            else:
                dx_global = p_dx * stitcher.draw_scale
                dy_global = p_dy * stitcher.draw_scale
                stitcher.current_x = stitcher.current_x - dx_global
                stitcher.current_y = stitcher.current_y - dy_global

                feature_score = cv2.countNonZero(match_mask)
                min_feature_score = 500
                if feature_score > min_feature_score:
                    stitcher.keyframe_mask = match_mask.copy()
                    stitcher.keyframe_pos = (stitcher.current_x, stitcher.current_y)
                    stitcher.stats["keyframe_switches"] += 1
                    print(f"[帧 {frame_num}] ⚓ Anchor更新 (Score: {feature_score})")
                else:
                    print(f"[帧 {frame_num}] ⚠️ 特征不足 ({feature_score})，跳过Anchor更新，仅F2F")

                match_success = True
                match_type = "F2F-Reset"
                current_quality = p_qual
        else:
            match_success = False
            stitcher.stats["failed_matches"] += 1
            print(f"[帧 {frame_num}] ❌ 配准完全失败 (K:{k_qual:.2f}, P:{p_qual:.2f})")

    stitcher.stats["match_quality"] = current_quality

    if match_success:
        stitcher.stats["successful_matches"] += 1

        if current_quality < stitcher.draw_quality_gate:
            stitcher.prev_mask = match_mask.copy()
            stitcher.prev_pos = (stitcher.current_x, stitcher.current_y)
            stitcher.stats["low_quality_skipped"] = stitcher.stats.get("low_quality_skipped", 0) + 1
            if frame_num % 10 == 0 or match_type == "F2F-Reset":
                print(
                    f"[帧 {frame_num}] 跳过落图 | {match_type} | "
                    f"Q:{current_quality:.2f} < Gate:{stitcher.draw_quality_gate:.2f}"
                )
            _update_match_rate(stitcher)
            return True

        prepared = prepare_scaled_frame_masks(
            save_mask,
            fog_mask,
            draw_scale=stitcher.draw_scale,
            wall_close_kernel_size=stitcher.wall_close_kernel_size,
        )
        px_scaled, py_scaled = scaled_player_pos(px, py, stitcher.draw_scale)
        stitcher._merge_frame_weighted(
            prepared["save_mask_scaled"],
            prepared["fog_mask_scaled"],
            prepared["h_scaled"],
            prepared["w_scaled"],
            px_scaled,
            py_scaled,
        )

        stitcher.prev_mask = match_mask.copy()
        stitcher.prev_pos = (stitcher.current_x, stitcher.current_y)

        if frame_num % 10 == 0 or match_type == "F2F-Reset":
            print(
                f"[帧 {frame_num}] ✅ {match_type} | "
                f"Q:{current_quality:.2f} | Pos:({stitcher.current_x:.1f}, {stitcher.current_y:.1f})"
            )

    _update_match_rate(stitcher)
    return True


def _update_match_rate(stitcher) -> None:
    if stitcher.stats["total_frames"] > 0:
        stitcher.stats["match_rate"] = (
            stitcher.stats["successful_matches"] / stitcher.stats["total_frames"]
        ) * 100.0
