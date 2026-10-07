"""Small route controller contract used before map-aware planning is wired."""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class RouteDecision:
    vector: tuple[float, float]
    duration_ms: int
    distance: float
    arrived: bool
    route: tuple[tuple[float, float], ...] = ()
    reason: str = ""


class StraightLineRouteController:
    """Return a bounded direction; map-aware steering is injected later."""

    def __init__(self, *, arrival_radius: float = 12.0, magnitude: float = 0.65, duration_ms: int = 80) -> None:
        if arrival_radius <= 0.0 or not 0.0 < magnitude <= 1.0 or duration_ms <= 0:
            raise ValueError("route controller parameters are invalid")
        self.arrival_radius = float(arrival_radius)
        self.magnitude = float(magnitude)
        self.duration_ms = int(duration_ms)

    def plan(self, position: tuple[float, float], target: tuple[float, float]) -> RouteDecision:
        dx = float(target[0]) - float(position[0])
        dy = float(target[1]) - float(position[1])
        distance = math.hypot(dx, dy)
        if not math.isfinite(distance):
            raise ValueError("route positions must be finite")
        if distance <= self.arrival_radius:
            return RouteDecision((0.0, 0.0), 0, distance, True, (target,), "within_arrival_radius")
        vector = (dx / distance * self.magnitude, dy / distance * self.magnitude)
        return RouteDecision(vector, self.duration_ms, distance, False, (target,), "direct_route")
