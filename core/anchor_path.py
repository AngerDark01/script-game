from __future__ import annotations

import math
from dataclasses import dataclass, field

from .path_utils import point_distance


@dataclass
class AnchorPathResult:
    path: list[tuple[int, int]]
    path_kind: str
    used_anchor_count: int = 0
    anchor_points: list[tuple[int, int]] = field(default_factory=list)


def plan_path_with_optional_anchors(
    *,
    wall_map,
    pathfinder,
    start_pos,
    target_pos,
    explored_map=None,
    anchors=None,
    max_anchors: int = 48,
    max_anchor_factor: float = 1.8,
    max_anchor_branching: int = 4,
    min_progress: float = 24.0,
    probe_distance: float = 84.0,
) -> AnchorPathResult | None:
    """Plan to target through the user's ordered anchor corridor.

    Guide points are not shortest-path graph nodes. They are user-authored
    route-shaping anchors, so this planner keeps their UI order and advances
    to the next forward anchor before trying the final target.
    """
    if wall_map is None or pathfinder is None:
        return None

    start = _int_point(start_pos)
    target = _int_point(target_pos)
    anchor_points = _ordered_corridor_anchors(
        start,
        target,
        anchors or [],
        max_anchors=max_anchors,
        min_progress=float(min_progress),
    )

    if anchor_points:
        next_anchor = anchor_points[0]
        anchor_segment = pathfinder.find_path(
            wall_map,
            start,
            next_anchor,
            explored_map=explored_map,
        )
        if anchor_segment:
            return AnchorPathResult(
                anchor_segment,
                "anchor_step",
                used_anchor_count=1,
                anchor_points=anchor_points,
            )
        probe = _probe_towards(start, next_anchor, float(probe_distance))
        return AnchorPathResult(
            [start, probe],
            "anchor_probe",
            used_anchor_count=1,
            anchor_points=anchor_points,
        )

    direct_path = pathfinder.find_path(wall_map, start, target, explored_map=explored_map)
    if direct_path:
        return AnchorPathResult(direct_path, "planned")

    return None


def _ordered_corridor_anchors(
    start: tuple[int, int],
    target: tuple[int, int],
    anchors,
    *,
    max_anchors: int,
    min_progress: float,
) -> list[tuple[int, int]]:
    ordered = _dedupe_anchor_order(anchors)
    if not ordered or max_anchors <= 0:
        return []

    reached_radius = max(4.0, min(8.0, float(min_progress) * 0.35))
    if len(ordered) == 1:
        anchor = ordered[0]
        if point_distance(start, anchor) <= reached_radius:
            return []
        if point_distance(anchor, target) <= point_distance(start, target) + reached_radius:
            return [anchor]
        return []

    cumulative = _anchor_cumulative_lengths(ordered)
    start_progress = _project_progress_on_polyline(start, ordered, cumulative)
    target_progress = _project_progress_on_polyline(target, ordered, cumulative)
    if target_progress <= start_progress + reached_radius:
        return []

    target_margin = max(reached_radius, 12.0)
    corridor = []
    for index, anchor in enumerate(ordered):
        progress = cumulative[index]
        if progress < start_progress - reached_radius:
            continue
        if progress <= start_progress + reached_radius and point_distance(start, anchor) <= reached_radius:
            continue
        if progress > target_progress + target_margin:
            continue
        corridor.append(anchor)
        if len(corridor) >= int(max_anchors):
            break
    return corridor


def anchor_route_progress(point, anchors) -> float | None:
    ordered = _dedupe_anchor_order(anchors)
    if not ordered:
        return None
    if len(ordered) == 1:
        return 0.0
    cumulative = _anchor_cumulative_lengths(ordered)
    return _project_progress_on_polyline(_int_point(point), ordered, cumulative)


def anchor_progress_map(anchors) -> dict[tuple[int, int], float]:
    ordered = _dedupe_anchor_order(anchors)
    cumulative = _anchor_cumulative_lengths(ordered)
    return {anchor: cumulative[index] for index, anchor in enumerate(ordered)}


def _dedupe_anchor_order(anchors) -> list[tuple[int, int]]:
    ordered = []
    seen = set()
    for raw_anchor in anchors:
        anchor = _int_point(raw_anchor)
        if anchor in seen:
            continue
        seen.add(anchor)
        ordered.append(anchor)
    return ordered


def _anchor_cumulative_lengths(anchors: list[tuple[int, int]]) -> list[float]:
    if not anchors:
        return []
    cumulative = [0.0]
    for index in range(1, len(anchors)):
        cumulative.append(cumulative[-1] + point_distance(anchors[index - 1], anchors[index]))
    return cumulative


def _project_progress_on_polyline(
    point: tuple[int, int],
    anchors: list[tuple[int, int]],
    cumulative: list[float],
) -> float:
    if len(anchors) <= 1:
        return 0.0

    px, py = float(point[0]), float(point[1])
    best_deviation = math.inf
    best_progress = 0.0
    for index in range(len(anchors) - 1):
        ax, ay = float(anchors[index][0]), float(anchors[index][1])
        bx, by = float(anchors[index + 1][0]), float(anchors[index + 1][1])
        vx, vy = bx - ax, by - ay
        seg_len_sq = vx * vx + vy * vy
        if seg_len_sq <= 1e-6:
            t = 0.0
        else:
            t = ((px - ax) * vx + (py - ay) * vy) / seg_len_sq
            t = max(0.0, min(1.0, t))
        proj_x = ax + vx * t
        proj_y = ay + vy * t
        deviation = math.hypot(px - proj_x, py - proj_y)
        progress = cumulative[index] + math.sqrt(seg_len_sq) * t
        if deviation < best_deviation:
            best_deviation = deviation
            best_progress = progress
    return best_progress


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
