from __future__ import annotations

from core.routing.geometry import interpolate_by_distance, point_distance, project_point_onto_path

from ..debug import nav_log
from ..models import MovementStep
from .utils import float_point, int_point


def movement_step(
    executor,
    *,
    task_id: str,
    current_pos,
    target_pos,
    wall_map,
    pathfinder,
    explored_map,
    now_ms: int,
    lookahead_distance: float,
    route_context=None,
    soft_anchors=None,
    force_repeat_click: bool = False,
    click_cooldown_ms: int | None = None,
    goal_stop_radius: float | None = None,
) -> MovementStep | None:
    current = float_point(current_pos)
    target = float_point(target_pos)
    executor._ensure_path(
        task_id=task_id,
        current_pos=current,
        target_pos=target,
        wall_map=wall_map,
        pathfinder=pathfinder,
        explored_map=explored_map,
        now_ms=int(now_ms),
        route_context=route_context,
        soft_anchors=soft_anchors,
    )
    if not executor.path or len(executor.path) < 2:
        nav_log(
            "nav movement path unavailable",
            task=task_id,
            player=int_point(current),
            target=int_point(target),
        )
        return None

    projection = project_point_onto_path(current, executor.path, executor.path_lengths)
    if projection is None:
        executor.last_plan_ms = 0
        nav_log(
            "nav movement projection failed",
            task=task_id,
            player=int_point(current),
            target=int_point(target),
        )
        return None

    subgoal = interpolate_by_distance(
        executor.path,
        executor.path_lengths,
        float(projection["distance"]) + float(lookahead_distance),
    )
    if subgoal is None:
        subgoal = executor.path[-1]
    executor.subgoal = float_point(subgoal)

    deviation = float(projection["distance_to_path"])
    final_goal_click = executor._should_use_exact_path_goal_click(current, goal_stop_radius=goal_stop_radius)
    base_click_cooldown_ms = (
        executor.click_cooldown_ms
        if click_cooldown_ms is None
        else max(0, int(click_cooldown_ms))
    )
    if final_goal_click:
        executor.subgoal = float_point(executor.path_goal)
        goal_key = int_point(executor.subgoal)
        if executor.final_goal_key != goal_key:
            executor.final_goal_key = goal_key
            executor.final_goal_since_ms = int(now_ms)
        # Near an anchor, normal movement clicks are too large because the
        # screen min radius is applied later. Click the mapped anchor point
        # and give the character a short settle window before any recovery.
        effective_cooldown_ms = max(
            base_click_cooldown_ms,
            max(0, int(getattr(executor, "exact_goal_click_cooldown_ms", base_click_cooldown_ms))),
        )
    else:
        executor.final_goal_key = None
        executor.final_goal_since_ms = 0
        effective_cooldown_ms = base_click_cooldown_ms

    cooldown_ready = executor.last_click_ms == 0 or int(now_ms) - executor.last_click_ms >= effective_cooldown_ms
    suppress_recovery = (
        final_goal_click
        and int(now_ms) - int(executor.final_goal_since_ms)
        < max(0, int(getattr(executor, "exact_goal_recovery_suppress_ms", 0)))
    )
    stuck = False if suppress_recovery else executor._is_stuck(float(projection["distance"]), int(now_ms))
    recovery_subgoal = None
    stuck_replan_requested = False
    if stuck and cooldown_ready and executor.recover_attempts < executor.max_recover_attempts:
        recovery_target = executor._active_recovery_target(target)
        recovery_subgoal = executor._recovery_probe(current, recovery_target, attempt=executor.recover_attempts)
        executor.subgoal = float_point(recovery_subgoal)
        executor.recover_attempts += 1
        nav_log(
            "nav movement stuck recovery",
            task=task_id,
            attempt=executor.recover_attempts,
            player=int_point(current),
            target=int_point(target),
            recovery_target=int_point(recovery_target),
            subgoal=int_point(executor.subgoal),
            path_kind=executor.path_kind,
            progress=round(float(projection["distance"]), 1),
            deviation=round(float(deviation), 1),
        )
    elif stuck and cooldown_ready:
        executor.force_replan = True
        executor.last_progress_value = None
        executor.last_progress_ms = int(now_ms)
        executor.recover_attempts = 0
        stuck_replan_requested = True
        nav_log(
            "nav movement stuck replan",
            task=task_id,
            player=int_point(current),
            target=int_point(target),
            path_kind=executor.path_kind,
            progress=round(float(projection["distance"]), 1),
            deviation=round(float(deviation), 1),
        )

    target_delta = (
        float("inf")
        if executor.last_click_target is None
        else point_distance(executor.last_click_target, executor.subgoal)
    )
    active_goal_pending = executor._active_path_goal_pending(current)
    can_use_regular_click = (
        not stuck_replan_requested
        and (
            bool(force_repeat_click)
            or final_goal_click
            or active_goal_pending
            or executor.last_click_target is None
            or target_delta >= executor.min_click_target_delta
            or deviation >= executor.path_deviation_threshold * 0.5
        )
    )
    should_click = cooldown_ready and (
        recovery_subgoal is not None
        or can_use_regular_click
    )
    if final_goal_click and should_click:
        final_goal_stop_radius = (
            (
                float(goal_stop_radius)
                if goal_stop_radius is not None
                else float(getattr(executor, "arrival_radius", executor.anchor_arrival_radius))
            )
            if executor.path_kind == "planned"
            else float(executor.anchor_arrival_radius)
        )
        nav_log(
            "nav movement exact path-goal click",
            task=task_id,
            path_kind=executor.path_kind,
            player=int_point(current),
            path_goal=int_point(executor.path_goal),
            distance=round(float(point_distance(current, executor.path_goal)), 1),
            stop_radius=round(final_goal_stop_radius, 1),
            anchor_arrival_radius=round(float(executor.anchor_arrival_radius), 1),
            movement_arrival_radius=round(float(getattr(executor, "arrival_radius", executor.anchor_arrival_radius)), 1),
            exact_radius=round(float(getattr(executor, "exact_goal_click_radius", 0.0)), 1),
            cooldown_ms=effective_cooldown_ms,
        )

    return MovementStep(
        path=list(executor.path),
        subgoal=executor.subgoal,
        path_kind=executor.path_kind,
        should_click=bool(should_click),
        force_click_target=bool(final_goal_click and recovery_subgoal is None),
        deviation=deviation,
        reason="move along shared executor",
        task_id=str(task_id),
        target_pos=target,
    )
