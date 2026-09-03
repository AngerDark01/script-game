from __future__ import annotations

from core.input.motion_mapping import (
    apply_bottom_click_guard,
    calculate_mapped_target_click,
    calculate_movement_click,
)


def move_to_map_target(controller, player_global_pos: tuple, target_global_pos: tuple):
    if not controller.control_enabled:
        print("Motion control is disabled. Skipping move.")
        return None

    if not controller.game_screen_center:
        print("Error: Game screen center is not calibrated.")
        return None

    target_screen_pos = controller._calculate_target_screen_position(
        player_global_pos,
        target_global_pos,
    )
    if target_screen_pos is None:
        print("Motion target is too close to click reliably.")
        return None

    controller._execute_click(target_screen_pos)
    return controller.last_click_info


def click_map_target_once(
    controller,
    player_global_pos: tuple,
    target_global_pos: tuple,
    reason: str = "force_click_target",
):
    if not controller.control_enabled:
        print("Motion control is disabled. Skipping target click.")
        return None

    if not controller.game_screen_center:
        print("Error: Game screen center is not calibrated.")
        return None

    target_screen_pos = controller._calculate_mapped_target_screen_position(
        player_global_pos,
        target_global_pos,
        reason=reason,
    )

    controller._execute_click(target_screen_pos)
    return controller.last_click_info


def calculate_target_screen_position(
    controller,
    player_global_pos: tuple,
    target_global_pos: tuple,
) -> tuple[int, int] | None:
    result = calculate_movement_click(
        player_global_pos=player_global_pos,
        target_global_pos=target_global_pos,
        game_screen_center=controller.game_screen_center,
        movement_scale_factor=controller.movement_scale_factor,
        movement_min_click_radius=controller.movement_min_click_radius,
        movement_max_click_radius=controller.movement_max_click_radius,
    )
    controller.last_click_info = result.click_info
    return result.screen_pos


def calculate_mapped_target_screen_position(
    controller,
    player_global_pos: tuple,
    target_global_pos: tuple,
    reason: str = "force_click_target",
) -> tuple[int, int]:
    result = calculate_mapped_target_click(
        player_global_pos=player_global_pos,
        target_global_pos=target_global_pos,
        game_screen_center=controller.game_screen_center,
        movement_scale_factor=controller.movement_scale_factor,
        movement_precision_click_max_radius=controller.movement_precision_click_max_radius,
        reason=reason,
    )
    controller.last_click_info = result.click_info
    return result.screen_pos


def apply_controller_bottom_click_guard(controller, screen_pos: tuple[int, int], driver=None):
    return apply_bottom_click_guard(
        screen_pos=screen_pos,
        game_screen_center=controller.game_screen_center,
        screen_height=controller._screen_height(driver),
        bottom_click_guard_pixels=controller.bottom_click_guard_pixels,
        bottom_click_guard_margin=controller.bottom_click_guard_margin,
    )
