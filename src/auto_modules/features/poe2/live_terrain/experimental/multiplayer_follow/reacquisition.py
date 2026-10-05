"""Short raw-map steering candidates for a temporarily unseen actor."""

from __future__ import annotations

import math
from dataclasses import dataclass

from auto_modules.core.routing.geometry import line_is_walkable, line_min_clearance


@dataclass(frozen=True, slots=True)
class ReacquisitionDecision:
    vector: tuple[float, float]
    score: float
    angle_degrees: float
    valid_candidates: int


def select_reacquisition_vector(
    position: tuple[float, float],
    target: tuple[float, float],
    last_visual: tuple[float, float],
    preferred_vector: tuple[float, float],
    *,
    walls,
    distance_map=None,
    previous_command: tuple[float, float] = (0.0, 0.0),
    horizon: float = 6.0,
) -> ReacquisitionDecision | None:
    """Favor progress and open space while leaving the last unseen region."""
    magnitude = min(0.45, math.hypot(*preferred_vector))
    goal_length = math.dist(position, target)
    if magnitude <= 1e-6 or goal_length <= 1e-6:
        return None
    base = (preferred_vector[0] / math.hypot(*preferred_vector),
            preferred_vector[1] / math.hypot(*preferred_vector))
    goal = ((target[0] - position[0]) / goal_length,
            (target[1] - position[1]) / goal_length)
    previous_length = math.hypot(*previous_command)
    prior = None if previous_length <= 1e-6 else (
        previous_command[0] / previous_length, previous_command[1] / previous_length,
    )
    origin_distance = math.dist(position, last_visual)
    options: list[tuple[float, float, tuple[float, float]]] = []
    for angle in (0.0, -30.0, 30.0, -60.0, 60.0, -90.0, 90.0):
        radians = math.radians(angle)
        direction = (
            base[0] * math.cos(radians) - base[1] * math.sin(radians),
            base[0] * math.sin(radians) + base[1] * math.cos(radians),
        )
        endpoint = (position[0] + direction[0] * horizon,
                    position[1] + direction[1] * horizon)
        if not line_is_walkable(walls, position, endpoint, corner_safe=True):
            continue
        clearance = line_min_clearance(walls, position, endpoint, distance_map=distance_map)
        exit_gain = max(-1.0, min(1.0, (math.dist(endpoint, last_visual) - origin_distance) / horizon))
        progress = direction[0] * goal[0] + direction[1] * goal[1]
        reversal = 0.0 if prior is None else max(0.0, -(direction[0] * prior[0] + direction[1] * prior[1]))
        score = (3.0 * progress + 0.8 * min(clearance / 8.0, 1.0)
                 + 0.6 * exit_gain - 0.5 * reversal - 0.15 * abs(angle) / 90.0)
        options.append((score, angle, direction))
    if not options:
        return None
    score, angle, direction = max(options, key=lambda item: (item[0], -abs(item[1])))
    return ReacquisitionDecision(
        (direction[0] * magnitude, direction[1] * magnitude),
        score, angle, len(options),
    )


__all__ = ["ReacquisitionDecision", "select_reacquisition_vector"]
