from __future__ import annotations

import math
from typing import NamedTuple


class ClickMappingResult(NamedTuple):
    screen_pos: tuple[int, int] | None
    click_info: dict


def calculate_movement_click(
    *,
    player_global_pos: tuple,
    target_global_pos: tuple,
    game_screen_center: tuple,
    movement_scale_factor: float,
    movement_min_click_radius: int,
    movement_max_click_radius: int,
) -> ClickMappingResult:
    """Map a normal movement target to a calibrated screen click."""
    delta_map_x = float(target_global_pos[0]) - float(player_global_pos[0])
    delta_map_y = float(target_global_pos[1]) - float(player_global_pos[1])
    map_distance = math.hypot(delta_map_x, delta_map_y)
    if map_distance < 1e-6:
        return ClickMappingResult(
            screen_pos=None,
            click_info={
                "map_delta": (delta_map_x, delta_map_y),
                "map_distance": map_distance,
                "screen_radius": 0.0,
                "screen_pos": None,
            },
        )

    raw_screen_radius = map_distance * float(movement_scale_factor)
    screen_radius = min(
        max(raw_screen_radius, int(movement_min_click_radius)),
        int(movement_max_click_radius),
    )
    direction_x = delta_map_x / map_distance
    direction_y = delta_map_y / map_distance
    screen_pos = _project_screen_pos(
        game_screen_center,
        direction_x=direction_x,
        direction_y=direction_y,
        screen_radius=screen_radius,
    )
    return ClickMappingResult(
        screen_pos=screen_pos,
        click_info={
            "map_delta": (delta_map_x, delta_map_y),
            "map_distance": map_distance,
            "raw_screen_radius": raw_screen_radius,
            "screen_radius": screen_radius,
            "direction": (direction_x, direction_y),
            "screen_pos": screen_pos,
        },
    )


def calculate_mapped_target_click(
    *,
    player_global_pos: tuple,
    target_global_pos: tuple,
    game_screen_center: tuple,
    movement_scale_factor: float,
    movement_precision_click_max_radius: int,
    reason: str,
) -> ClickMappingResult:
    """Map an exact target without applying the normal movement minimum radius."""
    delta_map_x = float(target_global_pos[0]) - float(player_global_pos[0])
    delta_map_y = float(target_global_pos[1]) - float(player_global_pos[1])
    map_distance = math.hypot(delta_map_x, delta_map_y)
    direction_x = 0.0
    direction_y = 0.0
    if map_distance > 1e-6:
        direction_x = delta_map_x / map_distance
        direction_y = delta_map_y / map_distance

    raw_screen_radius = map_distance * float(movement_scale_factor)
    precision_cap = float(movement_precision_click_max_radius)
    screen_radius = min(max(raw_screen_radius, 0.0), precision_cap)
    screen_pos = _project_screen_pos(
        game_screen_center,
        direction_x=direction_x,
        direction_y=direction_y,
        screen_radius=screen_radius,
    )
    return ClickMappingResult(
        screen_pos=screen_pos,
        click_info={
            "map_delta": (delta_map_x, delta_map_y),
            "map_distance": map_distance,
            "raw_screen_radius": raw_screen_radius,
            "screen_radius": screen_radius,
            "precision_radius_cap": precision_cap,
            "direction": (direction_x, direction_y),
            "screen_pos": screen_pos,
            "mapped_target_click": True,
            "reason": reason,
        },
    )


def apply_bottom_click_guard(
    *,
    screen_pos: tuple[int, int],
    game_screen_center: tuple | None,
    screen_height: int | None,
    bottom_click_guard_pixels: int,
    bottom_click_guard_margin: int,
) -> tuple[tuple[int, int], dict]:
    """Shorten downward clicks that would land in the bottom UI region."""
    info = {
        "enabled": int(bottom_click_guard_pixels) > 0,
        "applied": False,
    }
    if not info["enabled"] or not game_screen_center:
        return screen_pos, info

    if not screen_height:
        info["reason"] = "no_screen_height"
        return screen_pos, info

    forbidden_top = int(screen_height) - int(bottom_click_guard_pixels)
    safe_y = forbidden_top - max(0, int(bottom_click_guard_margin))
    x, y = int(screen_pos[0]), int(screen_pos[1])
    info.update({
        "screen_height": int(screen_height),
        "forbidden_top": forbidden_top,
        "safe_y": safe_y,
    })
    if y <= safe_y:
        return screen_pos, info

    cx, cy = int(game_screen_center[0]), int(game_screen_center[1])
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


def _project_screen_pos(
    game_screen_center: tuple,
    *,
    direction_x: float,
    direction_y: float,
    screen_radius: float,
) -> tuple[int, int]:
    target_screen_x = float(game_screen_center[0]) + direction_x * screen_radius
    target_screen_y = float(game_screen_center[1]) + direction_y * screen_radius
    return (int(round(target_screen_x)), int(round(target_screen_y)))
