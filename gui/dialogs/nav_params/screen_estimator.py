from __future__ import annotations

from typing import NamedTuple


class ClickRadiusEstimate(NamedTuple):
    min_radius: int
    max_radius: int


def estimate_click_radii(
    center: tuple[int, int],
    screen_bounds: tuple[int, int, int, int],
) -> ClickRadiusEstimate | None:
    """Estimate safe click radii from a physical center and screen bounds."""
    cx, cy = center
    left, top, right, bottom = screen_bounds
    safe_radius = min(cx - left, right - cx, cy - top, bottom - cy)

    if safe_radius <= 0:
        return None

    max_radius = max(180, min(900, int(safe_radius * 0.70)))
    min_radius = max(120, int(max_radius * 0.55))
    return ClickRadiusEstimate(min_radius=min_radius, max_radius=max_radius)
