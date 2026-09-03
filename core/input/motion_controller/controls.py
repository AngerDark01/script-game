from __future__ import annotations

import pydirectinput


def set_params(
    controller,
    game_screen_center: tuple,
    movement_scale_factor: float,
    movement_min_click_radius: int = 180,
    movement_max_click_radius: int = 360,
    movement_precision_click_max_radius: int = 180,
    bottom_click_guard_pixels: int = 300,
) -> None:
    controller.game_screen_center = game_screen_center
    controller.movement_scale_factor = float(movement_scale_factor)
    controller.movement_min_click_radius = max(0, int(movement_min_click_radius))
    controller.movement_max_click_radius = max(
        controller.movement_min_click_radius,
        int(movement_max_click_radius),
    )
    controller.movement_precision_click_max_radius = max(
        0,
        min(int(movement_precision_click_max_radius), controller.movement_max_click_radius),
    )
    controller.bottom_click_guard_pixels = max(0, int(bottom_click_guard_pixels))


def set_control_enabled(controller, enabled: bool) -> None:
    controller.control_enabled = enabled
    print(f"Motion Control Enabled: {enabled}")


def click_screen_position(controller, screen_pos: tuple[int, int], reason: str = "direct_screen_click"):
    if not controller.control_enabled:
        print("Motion control is disabled. Skipping screen click.")
        return None
    requested = (int(screen_pos[0]), int(screen_pos[1]))
    controller.last_click_info = {
        "map_delta": (0.0, 0.0),
        "map_distance": 0.0,
        "raw_screen_radius": 0.0,
        "screen_radius": 0.0,
        "direction": (0.0, 0.0),
        "screen_pos": requested,
        "reason": reason,
    }
    controller._execute_click(requested)
    return controller.last_click_info


def press_key(controller, key: str, reason: str = "event_key"):
    if not controller.control_enabled:
        print("Motion control is disabled. Skipping key press.")
        return None
    normalized_key = str(key).strip().lower()
    if not normalized_key:
        print("Empty key requested. Skipping key press.")
        return None
    print(f"Executing key press: key={normalized_key}, reason={reason}")
    pydirectinput.press(normalized_key)
    return {"key": normalized_key, "reason": reason}
