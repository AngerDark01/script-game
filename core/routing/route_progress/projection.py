from __future__ import annotations

import math

from .models import PolylineProjection


def build_cumulative_lengths(path) -> list[float]:
    if not path:
        return []

    cumulative = [0.0]
    for index in range(1, len(path)):
        cumulative.append(cumulative[-1] + _point_distance(path[index - 1], path[index]))
    return cumulative


def project_point_on_polyline(
    point,
    path,
    cumulative=None,
    *,
    degenerate_epsilon: float = 0.0,
) -> PolylineProjection | None:
    if not path:
        return None
    if len(path) == 1:
        anchor = _float_point(path[0])
        return PolylineProjection(
            point=anchor,
            progress=0.0,
            segment_index=0,
            deviation=_point_distance(point, anchor),
        )

    if cumulative is None or not cumulative:
        cumulative = build_cumulative_lengths(path)

    px, py = float(point[0]), float(point[1])
    best: PolylineProjection | None = None
    epsilon = float(degenerate_epsilon)

    for index in range(len(path) - 1):
        ax, ay = float(path[index][0]), float(path[index][1])
        bx, by = float(path[index + 1][0]), float(path[index + 1][1])
        vx, vy = bx - ax, by - ay
        seg_len_sq = vx * vx + vy * vy
        if seg_len_sq <= epsilon:
            ratio = 0.0
        else:
            ratio = ((px - ax) * vx + (py - ay) * vy) / seg_len_sq
            ratio = max(0.0, min(1.0, ratio))

        proj_x = ax + vx * ratio
        proj_y = ay + vy * ratio
        deviation = math.hypot(px - proj_x, py - proj_y)
        progress = float(cumulative[index]) + math.sqrt(seg_len_sq) * ratio

        candidate = PolylineProjection(
            point=(proj_x, proj_y),
            progress=float(progress),
            segment_index=index,
            deviation=float(deviation),
        )
        if best is None or candidate.deviation < best.deviation:
            best = candidate

    return best


def interpolate_by_distance(path, cumulative, distance):
    if not path:
        return None
    if len(path) == 1:
        return tuple(path[0])

    clamped = max(0.0, min(float(distance), cumulative[-1]))
    for index in range(len(cumulative) - 1):
        start_distance = cumulative[index]
        end_distance = cumulative[index + 1]
        if clamped <= end_distance:
            span = end_distance - start_distance
            ratio = 0.0 if span == 0 else (clamped - start_distance) / span
            ax, ay = path[index]
            bx, by = path[index + 1]
            return (ax + (bx - ax) * ratio, ay + (by - ay) * ratio)

    return tuple(path[-1])


def _point_distance(a, b) -> float:
    return math.hypot(float(a[0]) - float(b[0]), float(a[1]) - float(b[1]))


def _float_point(point) -> tuple[float, float]:
    return (float(point[0]), float(point[1]))
