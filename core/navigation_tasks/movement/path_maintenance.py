from __future__ import annotations

from core.routing.geometry import point_distance, project_point_onto_path

from ..debug import nav_log
from .utils import float_point, int_point


def ensure_movement_path(
    executor,
    *,
    task_id: str,
    current_pos,
    target_pos,
    wall_map,
    pathfinder,
    explored_map,
    now_ms: int,
    route_context=None,
    soft_anchors=None,
) -> None:
    target = float_point(target_pos)
    target_changed = executor.target is None or point_distance(executor.target, target) > 12.0
    needs_plan = executor.force_replan or target_changed or not executor.path or len(executor.path) < 2

    if not needs_plan:
        if executor.path_kind in {"anchor_step", "anchor_probe", "fallback"} and executor.path_goal is not None:
            if point_distance(current_pos, executor.path_goal) <= executor.anchor_arrival_radius:
                needs_plan = True
        projection = project_point_onto_path(current_pos, executor.path, executor.path_lengths)
        if not needs_plan and (
            projection is None or float(projection["distance_to_path"]) > executor.path_deviation_threshold
        ):
            needs_plan = True
        elif (
            not needs_plan
            and executor.path_kind == "fallback"
            and now_ms - executor.last_plan_ms >= max(0, int(getattr(executor, "fallback_replan_interval_ms", 650)))
        ):
            needs_plan = True

    if not needs_plan:
        return
    if (
        not target_changed
        and executor.last_plan_ms
        and now_ms - executor.last_plan_ms < max(0, int(getattr(executor, "replan_throttle_ms", 260)))
    ):
        return

    path, lengths, path_kind = executor._plan_path(
        current_pos,
        target,
        wall_map,
        pathfinder,
        explored_map,
        route_context=route_context,
        soft_anchors=soft_anchors,
    )
    executor.path = path
    executor.path_lengths = lengths
    executor.target = target
    executor.path_kind = path_kind
    executor.path_goal = path[-1] if path else None
    executor.last_plan_ms = int(now_ms)
    executor.force_replan = False
    executor.subgoal = None
    executor.last_progress_value = None
    executor.last_progress_ms = int(now_ms)
    executor.recover_attempts = 0
    executor.final_goal_key = None
    executor.final_goal_since_ms = 0
    next_anchor = executor.path_anchor_points[0] if getattr(executor, "path_anchor_points", None) else None
    nav_log(
        "nav movement planned",
        task=task_id,
        target=int_point(target),
        path_kind=path_kind,
        path_goal=int_point(executor.path_goal) if executor.path_goal else None,
        next_anchor=int_point(next_anchor) if next_anchor else None,
        anchor_count=len(getattr(executor, "path_anchor_points", []) or []),
        path_points=len(path),
        player=int_point(current_pos),
        direct_distance=round(float(point_distance(current_pos, target)), 1),
    )
