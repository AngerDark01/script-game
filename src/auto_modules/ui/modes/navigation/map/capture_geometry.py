from __future__ import annotations

from ....navigation_params import NavConfig


def physical_center_from_logical(logical_center, scale: tuple[float, float]) -> tuple[int, int] | None:
    if not logical_center:
        return None
    sx, sy = scale
    logical_x, logical_y = logical_center
    return int(logical_x * sx), int(logical_y * sy)


def initial_capture_center_for_config(
    nav_config: NavConfig | None,
    scale: tuple[float, float],
) -> tuple[tuple[int, int] | None, tuple[int, int]]:
    if not nav_config or not nav_config.monitor_logical_center:
        return None, (0, 0)
    physical_center = physical_center_from_logical(nav_config.monitor_logical_center, scale)
    return physical_center, physical_center or (0, 0)


def build_capture_geometry(nav_config: NavConfig | None, capture_center_physical):
    if not nav_config:
        return None, None, capture_center_physical

    size = nav_config.monitor_size
    region = nav_config.monitor_region

    if region:
        rect = {
            "left": int(region["left"]),
            "top": int(region["top"]),
            "width": int(region["width"]),
            "height": int(region["height"]),
        }
        return rect, None, capture_center_physical

    if not nav_config.monitor_logical_center or capture_center_physical is None:
        return None, None, capture_center_physical

    center_x, center_y = capture_center_physical
    half_size = size // 2
    rect = {
        "left": int(center_x - half_size),
        "top": int(center_y - half_size),
        "width": int(size),
        "height": int(size),
    }
    player_pos = (rect["width"] // 2, rect["height"] // 2)
    return rect, player_pos, capture_center_physical
