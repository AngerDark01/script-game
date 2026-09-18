from __future__ import annotations

from ..route_progress import build_cumulative_lengths, project_point_on_polyline
from .utils import _int_point


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
    return build_cumulative_lengths(anchors)


def _project_progress_on_polyline(
    point: tuple[int, int],
    anchors: list[tuple[int, int]],
    cumulative: list[float],
) -> float:
    if len(anchors) <= 1:
        return 0.0
    projection = project_point_on_polyline(
        point,
        anchors,
        cumulative,
        degenerate_epsilon=1e-6,
    )
    return 0.0 if projection is None else float(projection.progress)
