
import ast
from dataclasses import dataclass, field
from typing import List, Tuple

# Helper function to safely parse string representations of lists
def _parse_hsv_list(s: str, default: List[int]) -> List[int]:
    try:
        val = ast.literal_eval(s)
        if isinstance(val, list) and len(val) == 3:
            return val
    except (ValueError, SyntaxError):
        pass
    return default

@dataclass
class NavPreferences:
    k_ratio: float = 10.0
    y_bias: float = 1.0

@dataclass
class RecognizerParams:
    # --- Flags ---
    enable_wall: bool = True
    enable_fog: bool = True
    clahe_enabled: bool = True
    deepen_enabled: bool = True
    gamma_enabled: bool = False
    tophat_enabled: bool = False
    sat_filter_enabled: bool = False
    transparent_mode: bool = False

    # --- HSV Values ---
    wall_hsv_min: List[int] = field(default_factory=lambda: [0, 0, 0])
    wall_hsv_max: List[int] = field(default_factory=lambda: [255, 255, 255])
    fog_hsv_min: List[int] = field(default_factory=lambda: [91, 174, 188])
    fog_hsv_max: List[int] = field(default_factory=lambda: [108, 243, 255])
    player_hsv_min: List[int] = field(default_factory=lambda: [40, 100, 100])
    player_hsv_max: List[int] = field(default_factory=lambda: [80, 255, 255])

    # --- Numerical Values ---
    clahe_clip: float = 4.0
    clahe_grid: int = 4
    deepen_factor: float = 0.8
    blue_boost: float = 1.0
    gamma_value: float = 2.0
    tophat_strength: float = 4.0
    tophat_kernel_size: int = 15
    sat_filter_thresh: int = 50
    sat_filter_radius: int = 0
    edge_low: int = 50
    edge_high: int = 150
    wall_weight: int = 70
    edge_weight: int = 30
    trans_sat_penalty: float = 1.5
    trans_wall_thresh: int = 50
    kernel_small_size: int = 3
    kernel_medium_size: int = 5
    player_clear_radius: int = 22

@dataclass
class NavConfig:
    draw_scale: float = 2.0
    monitor_logical_center: Tuple[int, int] | None = None
    monitor_region: dict | None = None
    monitor_size: int = 320
    fps: int = 10
    game_screen_center: Tuple[int, int] | None = None
    movement_scale_factor: float = 1.0
    game_view_map_size: int = 520
    movement_min_click_radius: int = 180
    movement_max_click_radius: int = 360
    auto_click_cooldown_ms: int = 260
    auto_min_click_target_delta: float = 8.0
    anchor_arrival_radius: int = 26
    movement_progress_timeout_ms: int = 1200
    movement_min_progress_delta: float = 12.0
    movement_max_recover_attempts: int = 2
    movement_path_deviation_threshold: float = 96.0
    event_approach_enabled: bool = True
    event_visible_margin: int = 30
    event_approach_lookahead: int = 36
    event_approach_click_cooldown_ms: int = 800
    event_stop_radius: int = 18
    event_settle_ms: int = 800
    event_stable_frames: int = 2
    event_max_motion_per_frame: float = 8.0
    bottom_click_guard_pixels: int = 300
    nav_wall_erode_iterations: int = 1
    path_start_clear_radius: int = 30
    path_walkable_snap_radius: int = 18
    wall_match_close_kernel_size: int = 3
    coordinate_visual_check_interval_ms: int = 800
    coordinate_visual_check_margin: int = 140
    coordinate_visual_match_min_confidence: float = 0.72
    coordinate_visual_mismatch_threshold: float = 24.0
    coordinate_visual_mismatch_frames: int = 3
    nav_preferences: NavPreferences = field(default_factory=NavPreferences)
    recognizer_params: RecognizerParams = field(default_factory=RecognizerParams)

    @classmethod
    def from_dict(cls, data: dict):
        nav_prefs_data = data.get("nav_preferences", {})
        rec_params_data = data.get("recognizer_params", {})
        monitor_center = data.get("monitor_logical_center", data.get("monitor_center"))
        if monitor_center is not None and tuple(monitor_center) == (0, 0):
            monitor_center = None

        return cls(
            draw_scale=data.get("draw_scale", data.get("stitcher_params", {}).get("draw_scale", 2.0)),
            monitor_logical_center=tuple(monitor_center) if monitor_center is not None else None,
            monitor_region=data.get("monitor_region"),
            monitor_size=data.get("monitor_size", 320),
            fps=data.get("fps", 10),
            game_screen_center=data.get("game_screen_center", None),
            movement_scale_factor=data.get("movement_scale_factor", 1.0),
            game_view_map_size=data.get("game_view_map_size", 520),
            movement_min_click_radius=data.get("movement_min_click_radius", 180),
            movement_max_click_radius=data.get("movement_max_click_radius", 360),
            auto_click_cooldown_ms=data.get("auto_click_cooldown_ms", 260),
            auto_min_click_target_delta=data.get("auto_min_click_target_delta", 8.0),
            anchor_arrival_radius=data.get("anchor_arrival_radius", 26),
            movement_progress_timeout_ms=data.get("movement_progress_timeout_ms", 1200),
            movement_min_progress_delta=data.get("movement_min_progress_delta", 12.0),
            movement_max_recover_attempts=data.get("movement_max_recover_attempts", 2),
            movement_path_deviation_threshold=data.get("movement_path_deviation_threshold", 96.0),
            event_approach_enabled=data.get("event_approach_enabled", True),
            event_visible_margin=data.get("event_visible_margin", 30),
            event_approach_lookahead=data.get("event_approach_lookahead", 36),
            event_approach_click_cooldown_ms=data.get("event_approach_click_cooldown_ms", 800),
            event_stop_radius=data.get("event_stop_radius", 18),
            event_settle_ms=data.get("event_settle_ms", 800),
            event_stable_frames=data.get("event_stable_frames", 2),
            event_max_motion_per_frame=data.get("event_max_motion_per_frame", 8.0),
            bottom_click_guard_pixels=data.get("bottom_click_guard_pixels", 300),
            nav_wall_erode_iterations=data.get("nav_wall_erode_iterations", 1),
            path_start_clear_radius=data.get("path_start_clear_radius", 30),
            path_walkable_snap_radius=data.get("path_walkable_snap_radius", 18),
            wall_match_close_kernel_size=data.get(
                "wall_match_close_kernel_size",
                data.get("stitcher_params", {}).get("wall_close_kernel_size", 3),
            ),
            coordinate_visual_check_interval_ms=data.get("coordinate_visual_check_interval_ms", 800),
            coordinate_visual_check_margin=data.get("coordinate_visual_check_margin", 140),
            coordinate_visual_match_min_confidence=data.get("coordinate_visual_match_min_confidence", 0.72),
            coordinate_visual_mismatch_threshold=data.get("coordinate_visual_mismatch_threshold", 24.0),
            coordinate_visual_mismatch_frames=data.get("coordinate_visual_mismatch_frames", 3),
            nav_preferences=NavPreferences(**nav_prefs_data),
            recognizer_params=RecognizerParams(**rec_params_data)
        )

    def to_dict(self):
        return {
            "draw_scale": self.draw_scale,
            "monitor_logical_center": self.monitor_logical_center,
            "monitor_region": self.monitor_region,
            "monitor_size": self.monitor_size,
            "fps": self.fps,
            "game_screen_center": self.game_screen_center,
            "movement_scale_factor": self.movement_scale_factor,
            "game_view_map_size": self.game_view_map_size,
            "movement_min_click_radius": self.movement_min_click_radius,
            "movement_max_click_radius": self.movement_max_click_radius,
            "auto_click_cooldown_ms": self.auto_click_cooldown_ms,
            "auto_min_click_target_delta": self.auto_min_click_target_delta,
            "anchor_arrival_radius": self.anchor_arrival_radius,
            "movement_progress_timeout_ms": self.movement_progress_timeout_ms,
            "movement_min_progress_delta": self.movement_min_progress_delta,
            "movement_max_recover_attempts": self.movement_max_recover_attempts,
            "movement_path_deviation_threshold": self.movement_path_deviation_threshold,
            "event_approach_enabled": self.event_approach_enabled,
            "event_visible_margin": self.event_visible_margin,
            "event_approach_lookahead": self.event_approach_lookahead,
            "event_approach_click_cooldown_ms": self.event_approach_click_cooldown_ms,
            "event_stop_radius": self.event_stop_radius,
            "event_settle_ms": self.event_settle_ms,
            "event_stable_frames": self.event_stable_frames,
            "event_max_motion_per_frame": self.event_max_motion_per_frame,
            "bottom_click_guard_pixels": self.bottom_click_guard_pixels,
            "nav_wall_erode_iterations": self.nav_wall_erode_iterations,
            "path_start_clear_radius": self.path_start_clear_radius,
            "path_walkable_snap_radius": self.path_walkable_snap_radius,
            "wall_match_close_kernel_size": self.wall_match_close_kernel_size,
            "coordinate_visual_check_interval_ms": self.coordinate_visual_check_interval_ms,
            "coordinate_visual_check_margin": self.coordinate_visual_check_margin,
            "coordinate_visual_match_min_confidence": self.coordinate_visual_match_min_confidence,
            "coordinate_visual_mismatch_threshold": self.coordinate_visual_mismatch_threshold,
            "coordinate_visual_mismatch_frames": self.coordinate_visual_mismatch_frames,
            "nav_preferences": self.__dict__['nav_preferences'].__dict__,
            "recognizer_params": self.__dict__['recognizer_params'].__dict__,
        }
