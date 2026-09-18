from __future__ import annotations

from .corridor import _ordered_corridor_anchors
from .models import AnchorPathResult
from .utils import _int_point, _probe_towards


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
    """Plan to target through the user's ordered anchor corridor."""
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
