"""Ordered guide-anchor route shaping package."""

from .corridor import _ordered_corridor_anchors
from .models import AnchorPathResult
from .planner import plan_path_with_optional_anchors
from .progress import (
    _anchor_cumulative_lengths,
    _dedupe_anchor_order,
    _project_progress_on_polyline,
    anchor_progress_map,
    anchor_route_progress,
)
from .utils import _int_point, _probe_towards

__all__ = [
    "AnchorPathResult",
    "plan_path_with_optional_anchors",
    "anchor_route_progress",
    "anchor_progress_map",
    "_ordered_corridor_anchors",
    "_dedupe_anchor_order",
    "_anchor_cumulative_lengths",
    "_project_progress_on_polyline",
    "_probe_towards",
    "_int_point",
]
