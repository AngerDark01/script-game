"""Route planning and route persistence modules."""

from .anchors import (
    AnchorPathResult,
    anchor_progress_map,
    anchor_route_progress,
    plan_path_with_optional_anchors,
)
from .geometry import (
    build_cumulative_lengths,
    distance_to_path,
    interpolate_by_distance,
    is_inside_exit_region,
    line_is_walkable,
    line_clearance_stats,
    line_min_clearance,
    point_distance,
    project_point_onto_path,
    remove_collinear_points,
    shortcut_path,
    smooth_path,
)
from .obstacles import derive_navigation_wall_layer
from .pathfinder import PathFinder
from .local_controller import LocalMotionController, LocalMotionDecision
from .contact_evidence import ContactEvidence, ContactMonitor, ContactState
from .route_progress import PolylineProjection, project_point_on_polyline
from .route_repository import RouteManager
from .trajectory_target import LaggedTrajectoryTarget

__all__ = [
    "AnchorPathResult",
    "LaggedTrajectoryTarget",
    "PathFinder",
    "LocalMotionController",
    "LocalMotionDecision",
    "ContactEvidence",
    "ContactMonitor",
    "ContactState",
    "PolylineProjection",
    "RouteManager",
    "anchor_progress_map",
    "anchor_route_progress",
    "build_cumulative_lengths",
    "derive_navigation_wall_layer",
    "distance_to_path",
    "interpolate_by_distance",
    "is_inside_exit_region",
    "line_is_walkable",
    "line_clearance_stats",
    "line_min_clearance",
    "plan_path_with_optional_anchors",
    "point_distance",
    "project_point_on_polyline",
    "project_point_onto_path",
    "remove_collinear_points",
    "shortcut_path",
    "smooth_path",
]
