from __future__ import annotations

from core.navigation_tasks.models import NavigationIntent, NavigationIntentType

from ..debug import nav_log
from .geometry import int_point_or_none
from .models import EventApproachResult


def move_toward_event(
    approach,
    *,
    task,
    current,
    target,
    wall_map,
    pathfinder,
    explored_map,
    now_ms: int,
    lookahead_distance: float,
    route_context,
    movement,
    phase: str,
    click_cooldown_ms: int | None,
    goal_stop_radius: float | None = None,
) -> EventApproachResult:
    task_id = str(getattr(task, "id", "") or "")
    task_kind = getattr(getattr(task, "kind", None), "value", None)
    step = movement.step(
        task_id=task_id,
        current_pos=current,
        target_pos=target,
        wall_map=wall_map,
        pathfinder=pathfinder,
        explored_map=explored_map,
        now_ms=now_ms,
        lookahead_distance=lookahead_distance,
        route_context=route_context,
        click_cooldown_ms=click_cooldown_ms,
        goal_stop_radius=goal_stop_radius,
    )
    if step is None:
        nav_log(
            "event approach path unavailable",
            task=task_id,
            phase=phase,
            player=int_point_or_none(current),
            target=int_point_or_none(target),
        )
        return EventApproachResult(
            ready=False,
            phase=phase,
            reason="path unavailable",
            intent=NavigationIntent(
                type=NavigationIntentType.WAIT,
                task_id=task_id,
                task_kind=task_kind,
                player_pos=current,
                target_pos=target,
                message="event approach path unavailable",
            ),
        )

    intent_type = NavigationIntentType.MOVE_MAP if step.should_click and step.subgoal else NavigationIntentType.WAIT
    return EventApproachResult(
        ready=False,
        phase=phase,
        reason="moving to event",
        intent=NavigationIntent(
            type=intent_type,
            task_id=task_id,
            task_kind=task_kind,
            player_pos=current,
            target_pos=target,
            subgoal=step.subgoal,
            path=step.path,
            path_kind=step.path_kind,
            message="event approach move" if intent_type == NavigationIntentType.MOVE_MAP else "event approach hold",
            metadata={
                "deviation": step.deviation,
                "force_click_target": step.force_click_target,
                "event_approach_phase": phase,
            },
        ),
    )
