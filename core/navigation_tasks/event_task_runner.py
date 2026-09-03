from __future__ import annotations

from core.events.hooks import (
    EVENT_HOOK_COMPLETED,
    EVENT_HOOK_VISIBLE_TARGET,
    EventHookContext,
)
from core.events.models import EventActionType

from core.navigation_tasks.controller_utils import float_point, int_point
from core.navigation_tasks.debug import nav_log
from core.navigation_tasks.intent_factory import (
    event_action_intent,
    event_movement_step_intent,
    forced_event_move_intent,
)
from core.navigation_tasks.models import NavigationIntent, NavigationIntentType


def update_event_task(
    controller,
    task,
    event_coordinator,
    event_tick,
    wall_map,
    pathfinder,
    explored_map,
    now_ms: int,
    lookahead_distance: float,
) -> NavigationIntent:
    """Update a dynamic event task selected by NavigationTaskScheduler."""
    if event_coordinator is None or event_tick is None:
        return NavigationIntent(
            type=NavigationIntentType.WAIT,
            task_id=task.id,
            task_kind=task.kind.value,
            message="event context unavailable",
        )

    event_task_id = str(task.metadata.get("event_task_id") or "")
    if _navigation_approach_enabled(event_coordinator, task):
        if not controller.event_approach.is_released(task.id):
            approach = controller.event_approach.update(
                task=task,
                current_pos=controller.control_pos,
                wall_map=wall_map,
                pathfinder=pathfinder,
                explored_map=explored_map,
                now_ms=now_ms,
                lookahead_distance=lookahead_distance,
                route_context=controller.route_context,
                movement=controller.movement,
            )
            if approach.became_visible:
                _emit_event_hook(
                    controller,
                    EventHookContext(
                        hook_name=EVENT_HOOK_VISIBLE_TARGET,
                        now_ms=int(now_ms),
                        navigation_task_id=str(task.id),
                        event_task_id=event_task_id,
                        event_type=str(task.event_type or ""),
                        event_global_pos=int_point(task.target_pos),
                        player_global_pos=_float_point_or_none(controller.control_pos),
                        reason="event target entered real view",
                        metadata={
                            "phase": approach.phase,
                            "approach_target": approach.approach_target,
                        },
                    ),
                )
            if not approach.ready:
                return approach.intent or NavigationIntent(
                    type=NavigationIntentType.WAIT,
                    task_id=task.id,
                    task_kind=task.kind.value,
                    player_pos=controller.control_pos,
                    target_pos=task.target_pos,
                    message=approach.reason or "event approach blocked",
                )
            controller.event_approach.release_task(task.id)
            nav_log(
                "event approach released",
                task=task.id,
                event=task.event_type,
                player=int_point(controller.control_pos),
                target=int_point(task.target_pos),
            )
    else:
        controller.event_approach.finish_task(task.id)

    action = event_coordinator.run_task(event_task_id, event_tick)
    intent = event_action_intent(task=task, player_pos=controller.control_pos, action=action)
    if intent is not None:
        return intent

    if action.type == EventActionType.MOVE_TO:
        target = float_point(action.target_global_pos)
        if action.metadata.get("force_click_target"):
            return forced_event_move_intent(
                task=task,
                player_pos=controller.control_pos,
                target=target,
                action=action,
            )
        step = controller.movement.step(
            task_id=task.id,
            current_pos=controller.control_pos,
            target_pos=target,
            wall_map=wall_map,
            pathfinder=pathfinder,
            explored_map=explored_map,
            now_ms=now_ms,
            lookahead_distance=lookahead_distance,
            route_context=controller.route_context,
            force_repeat_click=bool(action.metadata.get("force_repeat_click", False)),
            goal_stop_radius=_action_goal_stop_radius(action, task),
        )
        return event_movement_step_intent(
            task=task,
            player_pos=controller.control_pos,
            target=target,
            step=step,
            action=action,
        )
    if action.type == EventActionType.COMPLETE:
        nav_log("nav event task completed", task=task.id, event=task.event_type)
        controller.event_approach.finish_task(task.id)
        controller.active_task_id = None
        controller.movement.reset()
        _emit_event_hook(
            controller,
            EventHookContext(
                hook_name=EVENT_HOOK_COMPLETED,
                now_ms=int(now_ms),
                navigation_task_id=str(task.id),
                event_task_id=event_task_id,
                event_type=str(task.event_type or ""),
                event_global_pos=int_point(task.target_pos),
                player_global_pos=_float_point_or_none(controller.control_pos),
                reason=action.reason or "event completed",
                metadata={
                    "event_action": action,
                    "action_metadata": dict(action.metadata or {}),
                },
            ),
        )
        return NavigationIntent(
            type=NavigationIntentType.WAIT,
            task_id=task.id,
            task_kind=task.kind.value,
            player_pos=controller.control_pos,
            target_pos=task.target_pos,
            message=action.reason or "event completed",
            metadata={"event_action": action, "terminal": True},
        )
    if action.type == EventActionType.FAIL:
        nav_log("nav event task failed", task=task.id, event=task.event_type, reason=action.reason)
        controller.event_approach.finish_task(task.id)
        controller.active_task_id = None
        controller.movement.reset()
        return NavigationIntent(
            type=NavigationIntentType.WAIT,
            task_id=task.id,
            task_kind=task.kind.value,
            player_pos=controller.control_pos,
            target_pos=task.target_pos,
            message=action.reason or "event failed",
            metadata={"event_action": action, "terminal": True},
        )

    return NavigationIntent(
        type=NavigationIntentType.WAIT,
        task_id=task.id,
        task_kind=task.kind.value,
        message="event action ignored",
    )


def _navigation_approach_enabled(event_coordinator, task) -> bool:
    config = getattr(event_coordinator, "config", None)
    event_type = str(getattr(task, "event_type", "") or "")
    event_config = config.event(event_type) if config is not None and hasattr(config, "event") else {}
    return bool((event_config or {}).get("navigation_approach_enabled", True))


def _emit_event_hook(controller, context: EventHookContext) -> None:
    hooks = getattr(controller, "event_hooks", None)
    if hooks is None:
        return
    hooks.emit(context)


def _action_goal_stop_radius(action, task) -> float | None:
    metadata = getattr(action, "metadata", {}) or {}
    radius = metadata.get("arrival_radius")
    if radius is None:
        task_metadata = getattr(task, "metadata", {}) or {}
        radius = task_metadata.get("event_stop_radius")
    if radius is None:
        radius = getattr(task, "radius", None)
    if radius is None:
        return None
    return max(4.0, float(radius))


def _float_point_or_none(point) -> tuple[float, float] | None:
    if point is None:
        return None
    return (float(point[0]), float(point[1]))
