from __future__ import annotations

from core.events.debug import describe_action, describe_task, event_log


def run_event_task(coordinator, task_id: str | None, tick):
    """Run or clear the selected event handler task."""
    if not getattr(coordinator.config, "enabled", True):
        if coordinator.runner.active_task is not None:
            coordinator.runner.update(None, tick, coordinator.config)
        coordinator.last_action = None
        return None

    if task_id is None:
        action = coordinator.runner.update(None, tick, coordinator.config)
        coordinator.last_action = action
        return action

    selected = find_enabled_task_by_id(coordinator, task_id)
    if selected is None:
        event_log("coordinator run_task missing", task_id=str(task_id))
        action = coordinator.runner.update(None, tick, coordinator.config)
        coordinator.last_action = action
        return action

    return run_selected_task(coordinator, selected, tick)


def find_enabled_task_by_id(coordinator, task_id: str):
    """Find an enabled active task by id."""
    for task in coordinator._enabled_active_tasks():
        if str(getattr(task, "id", "")) == str(task_id):
            return task
    return None


def run_selected_task(coordinator, task, tick):
    """Run the active handler and record the latest action."""
    action = coordinator.runner.update(task, tick, coordinator.config)
    coordinator.last_action = action
    if action is not None and coordinator._should_log(tick.now_ms, 750):
        event_log(
            "coordinator action",
            task=describe_task(task),
            action=describe_action(action),
        )
    return action
