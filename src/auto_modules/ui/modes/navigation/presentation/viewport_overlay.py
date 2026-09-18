from __future__ import annotations


def screen_overlay_geometry(capture_rect: dict | None, nav_config, scale: tuple[float, float]):
    if not capture_rect:
        return None, None

    sx, sy = scale
    rect = {
        "left": int(capture_rect["left"] / sx),
        "top": int(capture_rect["top"] / sy),
        "width": max(1, int(capture_rect["width"] / sx)),
        "height": max(1, int(capture_rect["height"] / sy)),
    }
    anchor = None
    if getattr(nav_config, "monitor_logical_center", None):
        anchor = (
            int(nav_config.monitor_logical_center[0]),
            int(nav_config.monitor_logical_center[1]),
        )
    return rect, anchor


def monitor_scene_rect(player_pos, capture_rect, player_local_pos, nav_core):
    if not player_pos or not capture_rect or not player_local_pos or not nav_core:
        return None

    offset_x, offset_y = nav_core.crop_offset
    rect_w = float(capture_rect["width"]) * nav_core.draw_scale
    rect_h = float(capture_rect["height"]) * nav_core.draw_scale
    player_local_x = float(player_local_pos[0]) * nav_core.draw_scale
    player_local_y = float(player_local_pos[1]) * nav_core.draw_scale

    rect_x = (float(player_pos[0]) - offset_x) - player_local_x
    rect_y = (float(player_pos[1]) - offset_y) - player_local_y
    return rect_x, rect_y, rect_w, rect_h


def game_view_scene_rect(player_pos, nav_core, nav_config):
    if not player_pos or not nav_core or not nav_config:
        return None

    size = float(getattr(nav_config, "game_view_map_size", 0) or 0)
    if size <= 0:
        return None

    offset_x, offset_y = nav_core.crop_offset
    half = size / 2.0
    rect_x = float(player_pos[0]) - offset_x - half
    rect_y = float(player_pos[1]) - offset_y - half
    return rect_x, rect_y, size, size
