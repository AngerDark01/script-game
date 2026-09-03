"""
地图拼接器 - 极简高精版 (Refactored)
去除冗余功能，回归核心算法，专注于 Frame-to-Frame + Keyframe Anchor 的高精度配准。
"""

from collections import deque

import numpy as np

from core.mapping.frame_preparation import (
    bounds_in_canvas,
    is_too_similar,
    prepare_scaled_frame_masks,
    scaled_player_pos,
    standardize_wall_thickness,
)
from core.mapping.frame_pipeline import add_frame_to_stitcher
from core.mapping.package_io import load_stitcher_map_package, save_stitcher_map_package
from core.mapping.performance import PerformanceMonitor
from core.mapping.rendering import get_cropped_map as render_cropped_map
from core.mapping.rendering import get_enhanced_map as render_enhanced_map
from core.mapping.weighted_merge import merge_frame_weighted
from core.vision.phase_displacement import estimate_phase_displacement


class MapStitcher:
    """
    实时地图拼接器 (Core Refactor)
    策略:
    - 尽可能与"关键帧"(Keyframe)进行配准，而不是上一帧。
    - 只有当与关键帧的重叠度降低时，才切换新的关键帧。
    - 这样可以将累积误差降低 N 倍 (N=关键帧间隔)。
    """

    def __init__(self, canvas_size=6000, draw_scale=2.0, wall_close_kernel_size=3):
        self.canvas_size = int(canvas_size)
        self.draw_scale = float(draw_scale)
        self.wall_close_kernel_size = max(1, int(wall_close_kernel_size))

        self.canvas = np.zeros((self.canvas_size, self.canvas_size), dtype=np.uint8)
        self.wall_layer = np.zeros((self.canvas_size, self.canvas_size), dtype=np.uint8)
        self.fog_layer = np.zeros((self.canvas_size, self.canvas_size), dtype=np.uint8)
        self.explored_map = np.zeros((self.canvas_size, self.canvas_size), dtype=np.uint8)
        self.weight_layer = np.zeros((self.canvas_size, self.canvas_size), dtype=np.float32)

        self.current_x = float(self.canvas_size // 2)
        self.current_y = float(self.canvas_size // 2)

        self.keyframe_mask = None
        self.keyframe_pos = (0.0, 0.0)
        self.keyframe_quality = 0.0

        self.prev_mask = None
        self.prev_pos = (0.0, 0.0)

        self.stats = {
            "total_frames": 0,
            "successful_matches": 0,
            "failed_matches": 0,
            "match_quality": 0.0,
            "match_rate": 0.0,
            "keyframe_switches": 0,
            "exploration": 0.0,
            "avg_displacement": 0.0,
        }

        self.perf = PerformanceMonitor()

        self.conf_thresh = 0.30
        self.keyframe_thresh = 0.25
        self.weight_add = 0.3
        self.weight_cap = 5.0
        self.draw_quality_gate = 0.35
        self.use_precise_visibility_mask = True
        self.precise_visibility_min_pixels = 16

        self.displacement_history = deque(maxlen=5)
        self.quality_history = deque(maxlen=5)

    def set_params(self, params):
        if "conf_thresh" in params:
            self.conf_thresh = float(params["conf_thresh"])
        if "keyframe_thresh" in params:
            self.keyframe_thresh = float(params["keyframe_thresh"])
        if "weight_add" in params:
            self.weight_add = float(params["weight_add"])
        if "weight_cap" in params:
            self.weight_cap = float(params["weight_cap"])
        if "draw_quality_gate" in params:
            self.draw_quality_gate = float(params["draw_quality_gate"])
        if "use_precise_visibility_mask" in params:
            self.use_precise_visibility_mask = bool(params["use_precise_visibility_mask"])
        if "precise_visibility_min_pixels" in params:
            self.precise_visibility_min_pixels = max(0, int(params["precise_visibility_min_pixels"]))
        if "wall_close_kernel_size" in params:
            self.wall_close_kernel_size = max(1, int(params["wall_close_kernel_size"]))

    def get_params(self):
        return {
            "conf_thresh": self.conf_thresh,
            "keyframe_thresh": self.keyframe_thresh,
            "weight_add": self.weight_add,
            "weight_cap": self.weight_cap,
            "draw_quality_gate": self.draw_quality_gate,
            "use_precise_visibility_mask": self.use_precise_visibility_mask,
            "precise_visibility_min_pixels": self.precise_visibility_min_pixels,
            "wall_close_kernel_size": self.wall_close_kernel_size,
            "canvas_size": self.canvas_size,
            "draw_scale": self.draw_scale,
        }

    def reinitialize_canvas(self, *, canvas_size=None, draw_scale=None, wall_close_kernel_size=None) -> None:
        self.__init__(
            canvas_size=int(canvas_size if canvas_size is not None else self.canvas_size),
            draw_scale=float(draw_scale if draw_scale is not None else self.draw_scale),
            wall_close_kernel_size=int(
                wall_close_kernel_size if wall_close_kernel_size is not None else self.wall_close_kernel_size
            ),
        )

    def save_map_package(self, folder_path):
        save_stitcher_map_package(self, folder_path)
        print(f"地图数据已保存至: {folder_path}")

    def load_map_package(self, folder_path):
        return load_stitcher_map_package(self, folder_path)

    def add_frame(self, img, match_mask, save_mask, fog_mask, raw_gray=None, player_pos=None):
        return add_frame_to_stitcher(self, img, match_mask, save_mask, fog_mask, raw_gray=raw_gray, player_pos=player_pos)

    def _smooth_displacement(self, dx, dy, quality):
        self.displacement_history.append((dx, dy))
        self.quality_history.append(quality)
        return dx, dy

    def _estimate_displacement(self, img1, img2):
        return estimate_phase_displacement(img1, img2)

    def _place_first_frame(self, save_mask, fog_mask, px, py):
        prepared = prepare_scaled_frame_masks(
            save_mask,
            fog_mask,
            draw_scale=self.draw_scale,
            wall_close_kernel_size=self.wall_close_kernel_size,
        )
        save_mask_scaled = prepared["save_mask_scaled"]
        fog_mask_scaled = prepared["fog_mask_scaled"]
        h_scaled = prepared["h_scaled"]
        w_scaled = prepared["w_scaled"]
        px_scaled, py_scaled = scaled_player_pos(px, py, self.draw_scale)
        self._merge_frame_weighted(save_mask_scaled, fog_mask_scaled, h_scaled, w_scaled, px_scaled, py_scaled, force=True)

    def _merge_frame_weighted(self, save_mask, fog_mask, h, w, px, py, force=False):
        merge_frame_weighted(self, save_mask, fog_mask, h, w, px, py, force=force)

    def _is_too_similar(self, roi_wall, save_mask):
        return is_too_similar(roi_wall, save_mask)

    def standardize_wall_thickness(self, mask):
        return standardize_wall_thickness(mask, self.wall_close_kernel_size)

    def _check_bounds(self, x1, y1, x2, y2):
        in_bounds = bounds_in_canvas(x1, y1, x2, y2, self.canvas_size)
        if not in_bounds:
            print(f"[警告] 触达地图边界! ({x1},{y1}) -> ({x2},{y2}) Canvas:{self.canvas_size}")
        return in_bounds

    def get_current_position(self):
        return (int(self.current_x), int(self.current_y))

    def get_statistics(self):
        return {
            **self.stats,
            "redundant_prevented": self.stats.get("redundant_prevented", 0),
            "low_quality_skipped": self.stats.get("low_quality_skipped", 0),
        }

    def reset(self):
        self.__init__(self.canvas_size, self.draw_scale)

    def get_cropped_map(self, margin=0):
        return render_cropped_map(self, margin=margin)

    def get_enhanced_map(self, margin=500):
        return render_enhanced_map(self, margin=margin)
