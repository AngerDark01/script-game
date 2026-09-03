from __future__ import annotations

from core.routing.geometry import point_distance

from core.navigation_tasks.models import NavigationIntent, NavigationIntentType

from .geometry import float_point_or_none, int_point_or_none
from .models import EventApproachResult


def update_event_approach(
    approach,
    *,
    task,
    current_pos,
    wall_map,
    pathfinder,
    explored_map,
    now_ms: int,
    lookahead_distance: float,
    route_context,
    movement,
) -> EventApproachResult:
    task_id = str(getattr(task, "id", "") or "")
    target = float_point_or_none(getattr(task, "target_pos", None))
    if not approach.config.enabled:
        return EventApproachResult(ready=True, phase="disabled", reason="event approach disabled")
    if current_pos is None or target is None:
        return EventApproachResult(
            ready=False,
            phase="waiting_localization",
            reason="waiting localization",
            intent=NavigationIntent(
                type=NavigationIntentType.WAIT,
                task_id=task_id,
                task_kind=getattr(getattr(task, "kind", None), "value", None),
                target_pos=target,
                message="event approach waiting localization",
            ),
        )

    if approach._task_id != task_id:
        approach.reset_active()
        approach._task_id = task_id

    current = float_point_or_none(current_pos)
    visible = approach._is_event_in_real_view(current, target)
    stop_radius = _task_stop_radius(approach, task)
    if not visible:
        approach._reset_settle()
        if approach._phase != "far":
            movement.force_replan = True
        result = approach._move_toward_event(
            task=task,
            current=current,
            target=target,
            wall_map=wall_map,
            pathfinder=pathfinder,
            explored_map=explored_map,
            now_ms=now_ms,
            lookahead_distance=lookahead_distance,
            route_context=route_context,
            movement=movement,
            phase="far",
            click_cooldown_ms=None,
            goal_stop_radius=stop_radius,
        )
        approach._log_phase(
            now_ms,
            "far",
            task=task_id,
            player=int_point_or_none(current),
            target=int_point_or_none(target),
            visible=False,
        )
        return result

    distance_to_event = point_distance(current, target)
    became_visible = approach._mark_visible_target(task_id)
    if distance_to_event <= stop_radius:
        result = approach._settle_or_ready(
            task=task,
            current=current,
            target=target,
            approach_target=target,
            now_ms=now_ms,
            distance=distance_to_event,
        )
        result.visible = True
        result.became_visible = became_visible
        return result

    if approach._phase not in {"approach", "settling", "ready"}:
        movement.force_replan = True
    move_result = approach._move_toward_event(
        task=task,
        current=current,
        target=target,
        wall_map=wall_map,
        pathfinder=pathfinder,
        explored_map=explored_map,
        now_ms=now_ms,
        lookahead_distance=float(approach.config.approach_lookahead),
        route_context=None,
        movement=movement,
        phase="approach",
        click_cooldown_ms=int(approach.config.click_cooldown_ms),
        goal_stop_radius=stop_radius,
    )
    step_path = move_result.intent.path if move_result.intent else []
    approach_target = approach._approach_target_from_path_with_stop_radius(step_path, target, stop_radius)
    distance_to_approach = (
        point_distance(current, approach_target)
        if approach_target is not None
        else distance_to_event
    )
    arrival_distance = min(distance_to_event, distance_to_approach)
    if arrival_distance <= stop_radius:
        result = approach._settle_or_ready(
            task=task,
            current=current,
            target=target,
            approach_target=approach_target or target,
            now_ms=now_ms,
            distance=arrival_distance,
        )
        result.visible = True
        result.became_visible = became_visible
        return result

    approach._reset_settle()
    approach._log_phase(
        now_ms,
        "approach",
        task=task_id,
        player=int_point_or_none(current),
        target=int_point_or_none(target),
        approach_target=int_point_or_none(approach_target),
        distance=round(float(distance_to_event), 1),
        visible=True,
    )
    move_result.visible = True
    move_result.became_visible = became_visible
    return move_result


def _task_stop_radius(approach, task) -> float:
    metadata = getattr(task, "metadata", {}) or {}
    radius = metadata.get("event_stop_radius")
    if radius is None:
        radius = getattr(task, "radius", None)
    if radius is None:
        return float(approach.config.stop_radius)
    return max(4.0, float(radius))
