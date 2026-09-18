from __future__ import annotations

from ..geometry import point_distance
from .progress import _anchor_cumulative_lengths, _dedupe_anchor_order, _project_progress_on_polyline


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
