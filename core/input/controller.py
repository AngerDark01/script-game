from __future__ import annotations

from core.input.click_pipeline import execute_click
from core.input.motion_controller import (
    apply_controller_bottom_click_guard,
    calculate_mapped_target_screen_position,
    calculate_target_screen_position,
    clamp_controller_screen_pos,
    click_map_target_once,
    click_screen_position,
    format_controller_window_info,
    get_input_driver,
    move_to_map_target,
    press_key,
    safe_pydirectinput_call,
    screen_height,
    send_controller_click,
    set_control_enabled,
    set_params,
)


class MotionController:
    """Convert map navigation targets into real screen clicks."""

    def __init__(self, input_driver=None):
        self.game_screen_center = None
        self.movement_scale_factor = 1.0
        self.movement_min_click_radius = 180
        self.movement_max_click_radius = 360
        self.movement_precision_click_max_radius = 180
        self.control_enabled = False
        self.last_click_info = None
        self.input_driver = input_driver
        self._input_driver_initialized = input_driver is not None
        self.screen_margin = 2
        self.click_hold_seconds = 0.05
        self.click_move_delay_seconds = 0.02
        self.input_backend = "win32_mouse_event"
        self.clamp_to_screen = False
        self.debug_click_target = True
        self.focus_before_click = False
        self.click_button = "primary"
        self.confirm_after_click = False
        self.confirm_click_delay_seconds = 0.08
        self.confirm_click_hold_seconds = 0.10
        self.bottom_click_guard_pixels = 300
        self.bottom_click_guard_margin = 20

    def set_params(
        self,
        game_screen_center: tuple,
        movement_scale_factor: float,
        movement_min_click_radius: int = 180,
        movement_max_click_radius: int = 360,
        movement_precision_click_max_radius: int = 180,
        bottom_click_guard_pixels: int = 300,
    ):
        """Set screen click mapping parameters."""
        return set_params(
            self,
            game_screen_center,
            movement_scale_factor,
            movement_min_click_radius=movement_min_click_radius,
            movement_max_click_radius=movement_max_click_radius,
            movement_precision_click_max_radius=movement_precision_click_max_radius,
            bottom_click_guard_pixels=bottom_click_guard_pixels,
        )

    def set_control_enabled(self, enabled: bool):
        """Enable or disable real mouse control."""
        return set_control_enabled(self, enabled)

    def move_to_map_target(self, player_global_pos: tuple, target_global_pos: tuple):
        """Click in the map-target direction using a calibrated screen radius."""
        return move_to_map_target(self, player_global_pos, target_global_pos)

    def click_map_target_once(
        self,
        player_global_pos: tuple,
        target_global_pos: tuple,
        reason: str = "force_click_target",
    ):
        """Click a mapped target once, even when player and target nearly overlap."""
        return click_map_target_once(self, player_global_pos, target_global_pos, reason=reason)

    def click_screen_position(self, screen_pos: tuple[int, int], reason: str = "direct_screen_click"):
        """Click an explicit screen position, used by event interactions."""
        return click_screen_position(self, screen_pos, reason=reason)

    def press_key(self, key: str, reason: str = "event_key"):
        """Press a keyboard key for event interactions."""
        return press_key(self, key, reason=reason)

    def _calculate_target_screen_position(
        self,
        player_global_pos: tuple,
        target_global_pos: tuple,
    ) -> tuple[int, int] | None:
        """Map a global-map direction to a screen click around the character."""
        return calculate_target_screen_position(self, player_global_pos, target_global_pos)

    def _calculate_mapped_target_screen_position(
        self,
        player_global_pos: tuple,
        target_global_pos: tuple,
        reason: str = "force_click_target",
    ) -> tuple[int, int]:
        """Map a global target to screen space without applying movement min radius."""
        return calculate_mapped_target_screen_position(self, player_global_pos, target_global_pos, reason=reason)

    def _execute_click(self, screen_pos: tuple[int, int]):
        """Execute a real mouse click."""
        execute_click(self, screen_pos)

    def _apply_bottom_click_guard(self, screen_pos: tuple[int, int], driver=None):
        """Shorten downward clicks that would land in the game's bottom UI."""
        return apply_controller_bottom_click_guard(self, screen_pos, driver=driver)

    def _screen_height(self, driver=None):
        return screen_height(self, driver)

    def _send_click(self, x: int, y: int, driver=None):
        """Send the movement click using the backend proven by the admin probe."""
        send_controller_click(self, x, y, driver=driver)

    def _get_input_driver(self):
        """Create the Windows input driver lazily so tests can run without side effects."""
        return get_input_driver(self)

    def _clamp_screen_pos(self, screen_pos: tuple[int, int]) -> tuple[int, int]:
        """Optionally keep click coordinates inside the process-visible screen."""
        return clamp_controller_screen_pos(self, screen_pos)

    def _safe_pydirectinput_call(self, name: str):
        return safe_pydirectinput_call(name)

    @staticmethod
    def _format_window_info(window_info):
        return format_controller_window_info(window_info)
