import math
import time

import pydirectinput

try:
    from .input_driver import InputDriver
except Exception:  # pragma: no cover - non-Windows fallback
    InputDriver = None


class MotionController:
    """Convert map navigation targets into real screen clicks."""

    def __init__(self, input_driver=None):
        self.game_screen_center = None
        self.movement_scale_factor = 1.0
        self.movement_min_click_radius = 180
        self.movement_max_click_radius = 360
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
        bottom_click_guard_pixels: int = 300,
    ):
        """Set screen click mapping parameters."""
        self.game_screen_center = game_screen_center
        self.movement_scale_factor = float(movement_scale_factor)
        self.movement_min_click_radius = max(0, int(movement_min_click_radius))
        self.movement_max_click_radius = max(
            self.movement_min_click_radius,
            int(movement_max_click_radius),
        )
        self.bottom_click_guard_pixels = max(0, int(bottom_click_guard_pixels))

    def set_control_enabled(self, enabled: bool):
        """Enable or disable real mouse control."""
        self.control_enabled = enabled
        print(f"Motion Control Enabled: {enabled}")

    def move_to_map_target(self, player_global_pos: tuple, target_global_pos: tuple):
        """Click in the map-target direction using a calibrated screen radius."""
        if not self.control_enabled:
            print("Motion control is disabled. Skipping move.")
            return None

        if not self.game_screen_center:
            print("Error: Game screen center is not calibrated.")
            return None

        target_screen_pos = self._calculate_target_screen_position(
            player_global_pos,
            target_global_pos,
        )
        if target_screen_pos is None:
            print("Motion target is too close to click reliably.")
            return None

        self._execute_click(target_screen_pos)
        return self.last_click_info

    def click_map_target_once(
        self,
        player_global_pos: tuple,
        target_global_pos: tuple,
        reason: str = "force_click_target",
    ):
        """Click a mapped target once, even when player and target nearly overlap."""
        if not self.control_enabled:
            print("Motion control is disabled. Skipping target click.")
            return None

        if not self.game_screen_center:
            print("Error: Game screen center is not calibrated.")
            return None

        target_screen_pos = self._calculate_mapped_target_screen_position(
            player_global_pos,
            target_global_pos,
            reason=reason,
        )

        self._execute_click(target_screen_pos)
        return self.last_click_info

    def click_screen_position(self, screen_pos: tuple[int, int], reason: str = "direct_screen_click"):
        """Click an explicit screen position, used by event interactions."""
        if not self.control_enabled:
            print("Motion control is disabled. Skipping screen click.")
            return None
        requested = (int(screen_pos[0]), int(screen_pos[1]))
        self.last_click_info = {
            "map_delta": (0.0, 0.0),
            "map_distance": 0.0,
            "raw_screen_radius": 0.0,
            "screen_radius": 0.0,
            "direction": (0.0, 0.0),
            "screen_pos": requested,
            "reason": reason,
        }
        self._execute_click(requested)
        return self.last_click_info

    def press_key(self, key: str, reason: str = "event_key"):
        """Press a keyboard key for event interactions."""
        if not self.control_enabled:
            print("Motion control is disabled. Skipping key press.")
            return None
        normalized_key = str(key).strip().lower()
        if not normalized_key:
            print("Empty key requested. Skipping key press.")
            return None
        print(f"Executing key press: key={normalized_key}, reason={reason}")
        pydirectinput.press(normalized_key)
        return {"key": normalized_key, "reason": reason}

    def _calculate_target_screen_position(
        self,
        player_global_pos: tuple,
        target_global_pos: tuple,
    ) -> tuple[int, int] | None:
        """Map a global-map direction to a screen click around the character."""
        delta_map_x = float(target_global_pos[0]) - float(player_global_pos[0])
        delta_map_y = float(target_global_pos[1]) - float(player_global_pos[1])
        map_distance = math.hypot(delta_map_x, delta_map_y)
        if map_distance < 1e-6:
            self.last_click_info = {
                "map_delta": (delta_map_x, delta_map_y),
                "map_distance": map_distance,
                "screen_radius": 0.0,
                "screen_pos": None,
            }
            return None

        raw_screen_radius = map_distance * self.movement_scale_factor
        screen_radius = min(
            max(raw_screen_radius, self.movement_min_click_radius),
            self.movement_max_click_radius,
        )
        direction_x = delta_map_x / map_distance
        direction_y = delta_map_y / map_distance
        target_screen_x = self.game_screen_center[0] + direction_x * screen_radius
        target_screen_y = self.game_screen_center[1] + direction_y * screen_radius

        screen_pos = (int(round(target_screen_x)), int(round(target_screen_y)))
        self.last_click_info = {
            "map_delta": (delta_map_x, delta_map_y),
            "map_distance": map_distance,
            "raw_screen_radius": raw_screen_radius,
            "screen_radius": screen_radius,
            "direction": (direction_x, direction_y),
            "screen_pos": screen_pos,
        }
        return screen_pos

    def _calculate_mapped_target_screen_position(
        self,
        player_global_pos: tuple,
        target_global_pos: tuple,
        reason: str = "force_click_target",
    ) -> tuple[int, int]:
        """Map a global target to screen space without applying movement min radius."""
        delta_map_x = float(target_global_pos[0]) - float(player_global_pos[0])
        delta_map_y = float(target_global_pos[1]) - float(player_global_pos[1])
        map_distance = math.hypot(delta_map_x, delta_map_y)
        direction_x = 0.0
        direction_y = 0.0
        if map_distance > 1e-6:
            direction_x = delta_map_x / map_distance
            direction_y = delta_map_y / map_distance
        raw_screen_radius = map_distance * self.movement_scale_factor
        screen_radius = min(max(raw_screen_radius, 0.0), float(self.movement_max_click_radius))
        target_screen_x = self.game_screen_center[0] + direction_x * screen_radius
        target_screen_y = self.game_screen_center[1] + direction_y * screen_radius
        screen_pos = (int(round(target_screen_x)), int(round(target_screen_y)))
        self.last_click_info = {
            "map_delta": (delta_map_x, delta_map_y),
            "map_distance": map_distance,
            "raw_screen_radius": raw_screen_radius,
            "screen_radius": screen_radius,
            "direction": (direction_x, direction_y),
            "screen_pos": screen_pos,
            "mapped_target_click": True,
            "reason": reason,
        }
        return screen_pos

    def _execute_click(self, screen_pos: tuple[int, int]):
        """Execute a real mouse click."""
        requested_pos = (int(screen_pos[0]), int(screen_pos[1]))
        x, y = requested_pos
        driver = None
        focused_hwnd = None
        target_window = None
        if self.input_backend == "win32_mouse_event" or self.debug_click_target or self.focus_before_click:
            driver = self._get_input_driver()

        guarded_pos, guard_info = self._apply_bottom_click_guard((x, y), driver=driver)
        x, y = guarded_pos
        pre_clamp_pos = (x, y)
        if self.clamp_to_screen:
            x, y = self._clamp_screen_pos((x, y))
        clamped = pre_clamp_pos != (x, y)
        if self.last_click_info is not None:
            self.last_click_info["screen_pos_requested"] = requested_pos
            self.last_click_info["screen_pos_after_bottom_guard"] = pre_clamp_pos
            self.last_click_info["screen_pos"] = (x, y)
            self.last_click_info["screen_pos_clamped"] = clamped
            self.last_click_info["bottom_guard"] = guard_info
        map_delta = self.last_click_info.get("map_delta", (0.0, 0.0))
        foreground_window = None
        foreground_info = None
        clip_rect = None
        win_cursor_before = None
        if self.debug_click_target and driver:
            try:
                if hasattr(driver, "describe_window_at"):
                    target_window = driver.describe_window_at(x, y)
                elif hasattr(driver, "window_from_point"):
                    hwnd = driver.window_from_point(x, y)
                    target_window = {"hwnd": int(hwnd)} if hwnd else None
                if hasattr(driver, "foreground_window"):
                    foreground_window = driver.foreground_window()
                if hasattr(driver, "describe_window") and foreground_window:
                    foreground_info = driver.describe_window(foreground_window)
                if hasattr(driver, "clip_cursor_rect"):
                    clip_rect = driver.clip_cursor_rect()
                if hasattr(driver, "cursor_pos"):
                    win_cursor_before = driver.cursor_pos()
                if self.last_click_info is not None:
                    self.last_click_info["target_window"] = target_window
                    self.last_click_info["foreground_window"] = foreground_info
                    self.last_click_info["clip_cursor_rect"] = clip_rect
                    self.last_click_info["win_cursor_before"] = win_cursor_before
            except Exception as exc:
                print(f"Window diagnostic at click point failed: {exc}")
        if self.focus_before_click and driver and hasattr(driver, "focus_window_at"):
            try:
                focused_hwnd = driver.focus_window_at(x, y)
                self.last_click_info["focused_hwnd"] = focused_hwnd
            except Exception as exc:
                print(f"Window focus before click failed: {exc}")

        pydirect_size = self._safe_pydirectinput_call("size")
        cursor_before = self._safe_pydirectinput_call("position")
        if self.last_click_info is not None:
            self.last_click_info["pydirectinput_size"] = pydirect_size
            self.last_click_info["cursor_before"] = cursor_before

        print(
            "Executing movement click: "
            f"requested=({requested_pos[0]}, {requested_pos[1]}), "
            f"screen=({x}, {y}), "
            f"clamped={clamped}, "
            f"radius={self.last_click_info.get('screen_radius', 0):.1f}, "
            f"map_delta=({map_delta[0]:.1f}, {map_delta[1]:.1f}), "
            f"backend={self.input_backend}, "
            f"pydi_size={pydirect_size}, "
            f"cursor_before={cursor_before}, "
            f"win_cursor_before={win_cursor_before}, "
            f"bottom_guard={guard_info}, "
            f"target_window={self._format_window_info(target_window)}, "
            f"foreground={self._format_window_info(foreground_info)}, "
            f"clip={clip_rect}, "
            f"focused_hwnd={focused_hwnd}, "
            f"confirm={self.confirm_after_click}"
        )
        try:
            self._send_click(x, y, driver=driver)
            cursor_after = self._safe_pydirectinput_call("position")
            win_cursor_after = None
            if driver and hasattr(driver, "cursor_pos"):
                try:
                    win_cursor_after = driver.cursor_pos()
                except Exception:
                    win_cursor_after = None
            if self.last_click_info is not None:
                self.last_click_info["cursor_after"] = cursor_after
                self.last_click_info["win_cursor_after"] = win_cursor_after
            print(f"Movement click sent: cursor_after={cursor_after}, win_cursor_after={win_cursor_after}")
            return
        except Exception as exc:
            print(f"{self.input_backend} click failed, falling back to pydirectinput: {exc}")

        pydirectinput.click(x, y, button=self.click_button)

    def _apply_bottom_click_guard(self, screen_pos: tuple[int, int], driver=None):
        """Shorten downward clicks that would land in the game's bottom UI."""
        info = {
            "enabled": self.bottom_click_guard_pixels > 0,
            "applied": False,
        }
        if not info["enabled"] or not self.game_screen_center:
            return screen_pos, info

        screen_height = self._screen_height(driver)
        if not screen_height:
            info["reason"] = "no_screen_height"
            return screen_pos, info

        forbidden_top = int(screen_height) - int(self.bottom_click_guard_pixels)
        safe_y = forbidden_top - max(0, int(self.bottom_click_guard_margin))
        x, y = int(screen_pos[0]), int(screen_pos[1])
        info.update({
            "screen_height": int(screen_height),
            "forbidden_top": forbidden_top,
            "safe_y": safe_y,
        })
        if y <= safe_y:
            return screen_pos, info

        cx, cy = int(self.game_screen_center[0]), int(self.game_screen_center[1])
        if y <= cy:
            return screen_pos, info

        ratio = (safe_y - cy) / float(y - cy)
        ratio = max(0.0, min(1.0, ratio))
        adjusted = (
            int(round(cx + (x - cx) * ratio)),
            int(round(cy + (y - cy) * ratio)),
        )
        info.update({
            "applied": True,
            "original": (x, y),
            "adjusted": adjusted,
            "ratio": ratio,
        })
        return adjusted, info

    def _screen_height(self, driver=None):
        if driver and getattr(driver, "screen_height", None):
            return int(driver.screen_height)
        size = self._safe_pydirectinput_call("size")
        if isinstance(size, tuple) and len(size) >= 2:
            return int(size[1])
        return None

    def _send_click(self, x: int, y: int, driver=None):
        """Send the movement click using the backend proven by the admin probe."""
        if self.input_backend == "win32_mouse_event" and driver and hasattr(driver, "click"):
            driver.click(
                x,
                y,
                button=self.click_button,
                hold_seconds=self.click_hold_seconds,
                move_delay=self.click_move_delay_seconds,
            )
            if self.last_click_info is not None:
                self.last_click_info["moved_by_driver"] = True
                self.last_click_info["confirm_click"] = False
            return

        if self.last_click_info is not None:
            self.last_click_info["moved_by_driver"] = False
        pydirectinput.click(x, y, button=self.click_button)
        if not self.confirm_after_click:
            if self.last_click_info is not None:
                self.last_click_info["confirm_click"] = False
            return

        time.sleep(max(0.0, float(self.confirm_click_delay_seconds)))
        if hasattr(pydirectinput, "mouseDown") and hasattr(pydirectinput, "mouseUp"):
            pydirectinput.mouseDown(button=self.click_button)
            time.sleep(max(0.0, float(self.confirm_click_hold_seconds)))
            pydirectinput.mouseUp(button=self.click_button)
        else:
            pydirectinput.click(button=self.click_button)

        if self.last_click_info is not None:
            self.last_click_info["confirm_click"] = True

    def _get_input_driver(self):
        """Create the Windows input driver lazily so tests can run without side effects."""
        if self._input_driver_initialized:
            return self.input_driver
        self._input_driver_initialized = True
        if InputDriver is None:
            self.input_driver = None
            return None
        try:
            self.input_driver = InputDriver()
        except Exception as exc:
            print(f"InputDriver unavailable, using pydirectinput fallback: {exc}")
            self.input_driver = None
        return self.input_driver

    def _clamp_screen_pos(self, screen_pos: tuple[int, int]) -> tuple[int, int]:
        """Optionally keep click coordinates inside the process-visible screen."""
        driver = self._get_input_driver()
        if not driver or not getattr(driver, "screen_width", None) or not getattr(driver, "screen_height", None):
            return screen_pos

        margin = max(0, int(self.screen_margin))
        max_x = max(0, int(driver.screen_width) - 1 - margin)
        max_y = max(0, int(driver.screen_height) - 1 - margin)
        min_x = min(margin, max_x)
        min_y = min(margin, max_y)
        x = min(max(int(screen_pos[0]), min_x), max_x)
        y = min(max(int(screen_pos[1]), min_y), max_y)
        return x, y

    def _safe_pydirectinput_call(self, name: str):
        func = getattr(pydirectinput, name, None)
        if not callable(func):
            return None
        try:
            return func()
        except Exception as exc:
            return f"{type(exc).__name__}: {exc}"

    @staticmethod
    def _format_window_info(window_info):
        if not window_info:
            return "None"
        hwnd = window_info.get("hwnd")
        pid = window_info.get("pid")
        class_name = window_info.get("class_name") or ""
        title = window_info.get("title") or ""
        if len(title) > 40:
            title = title[:37] + "..."
        return f"hwnd={hwnd},pid={pid},class='{class_name}',title='{title}'"
