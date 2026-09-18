"""Pure projection from world-map vectors into a game-view target point."""

from __future__ import annotations

from dataclasses import dataclass
import math


@dataclass(frozen=True)
class ProjectedViewTarget:
    """A view-space target derived from a world-space direction and distance."""

    point: tuple[int, int]
    direction: tuple[float, float]
    world_distance: float
    raw_radius: float
    radius: float


def project_world_target(
    *,
    player_position: tuple[float, float],
    target_position: tuple[float, float],
    view_center: tuple[float, float],
    pixels_per_world_unit: float,
    minimum_radius: float = 0.0,
    maximum_radius: float | None = None,
) -> ProjectedViewTarget:
    """Project a world target from the view centre, applying configurable radius limits."""
    player_x, player_y = _pair("player_position", player_position)
    target_x, target_y = _pair("target_position", target_position)
    center_x, center_y = _pair("view_center", view_center)
    if not math.isfinite(float(pixels_per_world_unit)) or float(pixels_per_world_unit) < 0:
        raise ValueError("pixels_per_world_unit must be a finite non-negative number")
    if not math.isfinite(float(minimum_radius)) or float(minimum_radius) < 0:
        raise ValueError("minimum_radius must be a finite non-negative number")
    if maximum_radius is not None and (
        not math.isfinite(float(maximum_radius)) or float(maximum_radius) < 0
    ):
        raise ValueError("maximum_radius must be a finite non-negative number")

    delta_x = target_x - player_x
    delta_y = target_y - player_y
    distance = math.hypot(delta_x, delta_y)
    raw_radius = distance * float(pixels_per_world_unit)
    if distance < 1e-6:
        direction = (0.0, 0.0)
    else:
        direction = (delta_x / distance, delta_y / distance)

    radius = max(raw_radius, float(minimum_radius))
    if maximum_radius is not None:
        radius = min(radius, float(maximum_radius))
    point = (
        int(round(center_x + direction[0] * radius)),
        int(round(center_y + direction[1] * radius)),
    )
    return ProjectedViewTarget(
        point=point,
        direction=direction,
        world_distance=distance,
        raw_radius=raw_radius,
        radius=radius,
    )


def _pair(name: str, value: tuple[float, float]) -> tuple[float, float]:
    if len(value) != 2:
        raise ValueError(f"{name} must contain exactly two coordinates")
    result = float(value[0]), float(value[1])
    if not all(math.isfinite(item) for item in result):
        raise ValueError(f"{name} coordinates must be finite")
    return result
