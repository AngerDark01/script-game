from __future__ import annotations

from core.routing.anchors import plan_path_with_optional_anchors
from core.routing.geometry import build_cumulative_lengths, point_distance, remove_collinear_points

from .utils import float_point, int_point


def plan_movement_path(
    executor,
    current_pos,
    target_pos,
    wall_map,
    pathfinder,
    explored_map,
    *,
    route_context=None,
    soft_anchors=None,
):
    current = int_point(current_pos)
    target = int_point(target_pos)
    anchors = executor._anchors_for_path(
        current_pos,
        target_pos,
        route_context=route_context,
        soft_anchors=soft_anchors,
    )

    path_result = None
    if wall_map is not None and pathfinder is not None:
        path_result = plan_path_with_optional_anchors(
            wall_map=wall_map,
            pathfinder=pathfinder,
            start_pos=current,
            target_pos=target,
            explored_map=explored_map,
            anchors=anchors,
        )

    if path_result and path_result.path:
        executor.path_anchor_points = [float_point(point) for point in path_result.anchor_points]
        path = [float_point(point) for point in remove_collinear_points(path_result.path)]
        if len(path) == 1:
            path.append(float_point(target_pos))
        return path, build_cumulative_lengths(path), path_result.path_kind

    raw_path = None
    if wall_map is not None and pathfinder is not None and not anchors:
        raw_path = pathfinder.find_path(
            wall_map,
            current,
            target,
            explored_map=explored_map,
        )

    if raw_path:
        executor.path_anchor_points = []
        path = [float_point(point) for point in remove_collinear_points(raw_path)]
        if len(path) == 1:
            path.append(float_point(target_pos))
        return path, build_cumulative_lengths(path), "planned"

    executor.path_anchor_points = []
    probe = executor._local_probe(current_pos, target_pos)
    path = [float_point(current_pos), float_point(probe)]
    return path, build_cumulative_lengths(path), "fallback"


def anchors_for_path(executor, current_pos, target_pos, *, route_context=None, soft_anchors=None):
    if route_context is not None:
        anchors = route_context.corridor_anchors(
            current_pos,
            target_pos,
            reached_radius=executor.anchor_arrival_radius,
            target_margin=max(float(getattr(executor, "route_anchor_target_margin", 36.0)), executor.anchor_arrival_radius),
        )
        if anchors:
            return anchors
    return list(soft_anchors or [])


def active_path_goal_pending(executor, current_pos) -> bool:
    if executor.path_goal is None:
        return False
    if executor.path_kind not in {"anchor_step", "anchor_probe", "fallback"}:
        return False
    return point_distance(current_pos, executor.path_goal) > executor.anchor_arrival_radius


def should_use_exact_path_goal_click(executor, current_pos, *, goal_stop_radius: float | None = None) -> bool:
    if not getattr(executor, "exact_goal_click_enabled", True):
        return False
    if executor.path_goal is None:
        return False
    if executor.path_kind not in {"anchor_step", "anchor_probe", "planned"}:
        return False
    if executor.path_kind == "planned" and (
        executor.target is None or point_distance(executor.path_goal, executor.target) > 12.0
    ):
        return False
    distance = point_distance(current_pos, executor.path_goal)
    exact_click_radius = max(0.0, float(getattr(executor, "exact_goal_click_radius", 0.0)))
    if exact_click_radius <= 0.0:
        return False
    if executor.path_kind == "planned":
        stop_radius = (
            float(goal_stop_radius)
            if goal_stop_radius is not None
            else float(getattr(executor, "arrival_radius", executor.anchor_arrival_radius))
        )
    else:
        stop_radius = float(executor.anchor_arrival_radius)
    if distance <= stop_radius:
        return False
    return distance <= exact_click_radius


def active_recovery_target(executor, final_target):
    if executor.path_goal is not None and executor.path_kind in {"anchor_step", "anchor_probe", "fallback"}:
        return executor.path_goal
    return final_target
