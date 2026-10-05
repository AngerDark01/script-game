"""PoE2 adapter that turns a wall mask into local contact evidence.

The adapter is intentionally limited to image interpretation.  It does not
choose a recovery route and it does not send input.  The follow runtime can
therefore consume the result in the same way as a future device or robot
sensor adapter.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

import numpy as np


@dataclass(frozen=True, slots=True)
class MinimapContactObservation:
    player_position: tuple[float, float]
    command_direction: tuple[float, float]
    wall_ahead: bool
    wall_distance: float | None
    free_left: float
    free_right: float
    sampled_pixels: int
    centerline_wall_distance: float | None = None
    blocking_wall_ahead: bool = False
    narrow_passage: bool = False
    escape_available: bool = False


def inspect_minimap_contact(
    wall_mask: Any,
    player_position: tuple[float, float],
    command_direction: tuple[float, float],
    *,
    lookahead: tuple[float, ...] = (6.0, 10.0, 14.0),
    beam_radius: int = 1,
    wall_threshold: float = 0.20,
) -> MinimapContactObservation:
    """Inspect a short beam and two lateral beams in the captured minimap.

    ``wall_mask`` is the already-produced wall layer (nonzero means wall).
    The returned distances are screen pixels and are suitable for diagnostics
    and recovery scoring; no game-specific colour thresholds live here.
    """
    mask = np.asarray(wall_mask)
    if mask.ndim != 2 or min(mask.shape) < 2:
        raise ValueError("wall_mask must be a two-dimensional image")
    px, py = float(player_position[0]), float(player_position[1])
    dx, dy = float(command_direction[0]), float(command_direction[1])
    norm = math.hypot(dx, dy)
    if norm <= 1e-6:
        return MinimapContactObservation((px, py), (0.0, 0.0), False, None, 0.0, 0.0, 0)
    ux, uy = dx / norm, dy / norm
    height, width = mask.shape

    def occupancy(x: float, y: float) -> float:
        return occupancy_with_radius(x, y, beam_radius)

    def occupancy_with_radius(x: float, y: float, radius: int) -> float:
        cx, cy = int(round(x)), int(round(y))
        values: list[float] = []
        for oy in range(-int(radius), int(radius) + 1):
            for ox in range(-int(radius), int(radius) + 1):
                sx, sy = cx + ox, cy + oy
                if 0 <= sx < width and 0 <= sy < height:
                    values.append(float(mask[sy, sx]) > 0.0)
        return sum(values) / len(values) if values else 1.0

    forward = []
    for distance in lookahead:
        distance = float(distance)
        if not math.isfinite(distance) or distance <= 0.0:
            continue
        forward.append((distance, occupancy(px + ux * distance, py + uy * distance)))
    wall_distance = next((distance for distance, ratio in forward if ratio >= wall_threshold), None)
    wall_ahead = wall_distance is not None
    # The beam is deliberately retained as a raw diagnostic.  A beam with a
    # radius can touch a nearby side wall even though the command centreline
    # is still open.  Only the centreline result is allowed to establish a
    # blocking contact for the generic movement runtime.
    centerline = []
    for distance, _ratio in forward:
        centerline.append(
            (distance, occupancy_with_radius(px + ux * distance, py + uy * distance, 0))
        )
    centerline_wall_distance = next(
        (distance for distance, ratio in centerline if ratio >= wall_threshold),
        None,
    )
    blocking_wall_ahead = centerline_wall_distance is not None
    narrow_passage = wall_ahead and not blocking_wall_ahead
    # A lateral beam is used only to tell the recovery controller which side
    # is open.  It never masks or alters the wall layer.
    left = (-uy, ux)
    right = (uy, -ux)

    def free_score(side: tuple[float, float]) -> float:
        samples = [occupancy(px + side[0] * distance, py + side[1] * distance) for distance in lookahead]
        return 1.0 - (sum(samples) / len(samples) if samples else 1.0)

    free_left = free_score(left)
    free_right = free_score(right)
    # This is a recovery hint, not proof that the actor is free.  A blocking
    # centreline with one open lateral sector should enter local recovery,
    # rather than escalate directly to global relocalisation.
    escape_available = free_left >= 0.55 or free_right >= 0.55

    return MinimapContactObservation(
        (px, py),
        (ux, uy),
        wall_ahead,
        wall_distance,
        free_left,
        free_right,
        len(forward),
        centerline_wall_distance,
        blocking_wall_ahead,
        narrow_passage,
        escape_available,
    )


__all__ = ["MinimapContactObservation", "inspect_minimap_contact"]
