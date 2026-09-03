from __future__ import annotations

from ..geometry import point_distance


def _probe_towards(
    start: tuple[int, int],
    target: tuple[int, int],
    distance: float,
) -> tuple[int, int]:
    total = point_distance(start, target)
    if total <= 1e-6 or total <= distance:
        return target
    ratio = max(0.0, min(1.0, float(distance) / total))
    return (
        int(round(float(start[0]) + (float(target[0]) - float(start[0])) * ratio)),
        int(round(float(start[1]) + (float(target[1]) - float(start[1])) * ratio)),
    )


def _int_point(point) -> tuple[int, int]:
    return int(round(float(point[0]))), int(round(float(point[1])))
