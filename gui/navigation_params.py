
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

@dataclass
class NavConfig:
    draw_scale: float = 2.0
    monitor_logical_center: Tuple[int, int] = (0, 0)
    monitor_size: int = 200
    fps: int = 10
    game_screen_center: Tuple[int, int] | None = None
    movement_scale_factor: float = 1.0
    nav_preferences: NavPreferences = field(default_factory=NavPreferences)
    recognizer_params: RecognizerParams = field(default_factory=RecognizerParams)

    @classmethod
    def from_dict(cls, data: dict):
        nav_prefs_data = data.get("nav_preferences", {})
        rec_params_data = data.get("recognizer_params", {})

        return cls(
            draw_scale=data.get("draw_scale", 2.0),
            monitor_logical_center=tuple(data.get("monitor_logical_center", data.get("monitor_center", (0, 0)))),
            monitor_size=data.get("monitor_size", 200),
            fps=data.get("fps", 10),
            game_screen_center=data.get("game_screen_center", None),
            movement_scale_factor=data.get("movement_scale_factor", 1.0),
            nav_preferences=NavPreferences(**nav_prefs_data),
            recognizer_params=RecognizerParams(**rec_params_data)
        )

    def to_dict(self):
        return {
            "draw_scale": self.draw_scale,
            "monitor_logical_center": self.monitor_logical_center,
            "monitor_size": self.monitor_size,
            "fps": self.fps,
            "game_screen_center": self.game_screen_center,
            "movement_scale_factor": self.movement_scale_factor,
            "nav_preferences": self.__dict__['nav_preferences'].__dict__,
            "recognizer_params": self.__dict__['recognizer_params'].__dict__,
        }
