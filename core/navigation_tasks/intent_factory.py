from __future__ import annotations

from core.events.models import EventActionType

from .models import NavigationIntent, NavigationIntentType


def movement_step_intent(*, task, player_pos, step, unavailable_message: str, move_message: str, wait_message: str):
    """Convert a MovementStep into a NavigationIntent."""
    if step is None:
        return NavigationIntent(
            type=NavigationIntentType.WAIT,
            task_id=task.id,
            task_kind=task.kind.value,
            player_pos=player_pos,
            target_pos=task.target_pos,
            message=unavailable_message,
        )
    intent_type = NavigationIntentType.MOVE_MAP if step.should_click and step.subgoal else NavigationIntentType.WAIT
    return NavigationIntent(
        type=intent_type,
        task_id=task.id,
        task_kind=task.kind.value,
        player_pos=player_pos,
        target_pos=task.target_pos,
        subgoal=step.subgoal,
        path=step.path,
        path_kind=step.path_kind,
        required_index=task.required_index,
        message=move_message if intent_type == NavigationIntentType.MOVE_MAP else wait_message,
        metadata={"deviation": step.deviation, "force_click_target": step.force_click_target},
    )


def forced_event_move_intent(*, task, player_pos, target, action):
    return NavigationIntent(
        type=NavigationIntentType.MOVE_MAP,
        task_id=task.id,
        task_kind=task.kind.value,
        player_pos=player_pos,
        target_pos=target,
        subgoal=target,
        path=[player_pos, target] if player_pos else [],
        path_kind="forced_target",
        message=action.reason or "event forced target click",
        metadata={"force_click_target": True, "event_action": action},
    )


def event_movement_step_intent(*, task, player_pos, target, step, action):
    if step is None:
        return NavigationIntent(
            type=NavigationIntentType.WAIT,
            task_id=task.id,
            task_kind=task.kind.value,
            player_pos=player_pos,
            target_pos=target,
            message="event path unavailable",
            metadata={"event_action": action},
        )
    intent_type = NavigationIntentType.MOVE_MAP if step.should_click and step.subgoal else NavigationIntentType.WAIT
    return NavigationIntent(
        type=intent_type,
        task_id=task.id,
        task_kind=task.kind.value,
        player_pos=player_pos,
        target_pos=target,
        subgoal=step.subgoal,
        path=step.path,
        path_kind=step.path_kind,
        message=action.reason or "event move",
        metadata={
            "event_action": action,
            "deviation": step.deviation,
            "force_click_target": step.force_click_target,
        },
    )


def event_action_intent(*, task, player_pos, action):
    """Convert non-movement EventAction values into NavigationIntent values."""
    if action is None or action.type == EventActionType.NONE:
        return NavigationIntent(
            type=NavigationIntentType.WAIT,
            task_id=task.id,
            task_kind=task.kind.value,
            player_pos=player_pos,
            target_pos=task.target_pos,
            message="event idle",
        )
    if action.type == EventActionType.CLICK_SCREEN:
        return NavigationIntent(
            type=NavigationIntentType.CLICK_SCREEN,
            task_id=task.id,
            task_kind=task.kind.value,
            player_pos=player_pos,
            target_pos=task.target_pos,
            message=action.reason or "event click screen",
            metadata={"event_action": action, "screen_pos": action.screen_pos},
        )
    if action.type == EventActionType.PRESS_KEY:
        return NavigationIntent(
            type=NavigationIntentType.PRESS_KEY,
            task_id=task.id,
            task_kind=task.kind.value,
            player_pos=player_pos,
            target_pos=task.target_pos,
            message=action.reason or "event press key",
            metadata={"event_action": action, "key": action.key},
        )
    if action.type == EventActionType.WAIT:
        metadata = {"event_action": action, "wait_ms": action.wait_ms}
        metadata.update(action.metadata or {})
        return NavigationIntent(
            type=NavigationIntentType.WAIT,
            task_id=task.id,
            task_kind=task.kind.value,
            player_pos=player_pos,
            target_pos=task.target_pos,
            message=action.reason or "event wait",
            metadata=metadata,
        )
    return None
