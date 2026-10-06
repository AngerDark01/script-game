"""Local projection of noisy targets onto the nearest walkable map cell."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

import numpy as np


@dataclass(frozen=True)
class ProjectedTarget:
    position: tuple[float, float]
    projected: bool
    diagnostics: dict[str, Any]


class WalkableTargetProjector:
    def __init__(self, wall_map: Any, *, radius: int = 8) -> None:
        grid = np.asarray(wall_map)
        if grid.ndim != 2 or min(grid.shape) < 2:
            raise ValueError("wall_map must be a two-dimensional grid")
        if radius < 1:
            raise ValueError("radius must be positive")
        self._walkable = np.asarray(grid == 0, dtype=bool)
        self._radius = int(radius)

    def project(self, point: tuple[float, float]) -> ProjectedTarget:
        x, y = float(point[0]), float(point[1])
        height, width = self._walkable.shape
        ix, iy = int(round(x)), int(round(y))
        if 0 <= ix < width and 0 <= iy < height and self._walkable[iy, ix]:
            return ProjectedTarget((x, y), False, {
                "projected": False, "status": "target_walkable", "original": (x, y),
            })
        candidates: list[tuple[float, float, float, int, int, int]] = []
        for radius in range(1, self._radius + 1):
            for cy in range(max(0, iy - radius), min(height, iy + radius + 1)):
                for cx in range(max(0, ix - radius), min(width, ix + radius + 1)):
                    if not self._walkable[cy, cx]:
                        continue
                    distance = math.hypot(float(cx) - x, float(cy) - y)
                    # Prefer a point with a little open space around it.  A
                    # nearest single pixel beside a wall is a poor target and
                    # caused the old projection to select false wall cells.
                    local = self._walkable[
                        max(0, cy - 1):min(height, cy + 2),
                        max(0, cx - 1):min(width, cx + 2),
                    ]
                    free_fraction = float(np.count_nonzero(local)) / max(1, local.size)
                    clearance = self._clearance(cx, cy)
                    # Distance is dominant; openness and clearance break ties
                    # without moving a target across a large region.
                    score = distance + (1.0 - free_fraction) * 2.5 + 1.0 / max(clearance, 1.0)
                    candidates.append((score, distance, clearance, cx, cy, radius))
        if not candidates:
            return ProjectedTarget(
                (x, y), False,
                {"projected": False, "status": "target_no_walkable_neighbor", "original": (x, y), "reason": "no_walkable_neighbor"},
            )
        candidates.sort()
        score, distance, clearance, cx, cy, selected_radius = candidates[0]
        projected = (float(cx), float(cy))
        return ProjectedTarget(
            projected,
            True,
            {
                "projected": True,
                "status": "target_projected",
                "original": (x, y),
                "projected_position": projected,
                "distance": float(distance),
                "score": float(score),
                "clearance": float(clearance),
                "neighbor_radius": int(selected_radius),
                "radius": self._radius,
            },
        )

    def _clearance(self, cx: int, cy: int) -> float:
        """Approximate local free-space radius in map cells."""
        height, width = self._walkable.shape
        for radius in range(1, min(self._radius, 12) + 1):
            y0, y1 = max(0, cy - radius), min(height, cy + radius + 1)
            x0, x1 = max(0, cx - radius), min(width, cx + radius + 1)
            if not bool(np.all(self._walkable[y0:y1, x0:x1])):
                return float(radius - 1)
        return float(min(self._radius, 12))


__all__ = ["ProjectedTarget", "WalkableTargetProjector"]
