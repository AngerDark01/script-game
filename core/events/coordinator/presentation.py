from __future__ import annotations

from core.events.debug import describe_action
from core.events.overlay_models import task_to_overlay


def build_overlays(coordinator):
    """Build UI overlay models for enabled display tasks."""
    if not getattr(coordinator.config, "enabled", True):
        return []
    overlays = []
    for task in coordinator._enabled_display_tasks():
        definition = coordinator.registry.get(task.event_type)
        overlays.append(task_to_overlay(task, definition))
    return overlays


def status_summary(coordinator) -> str:
    """Return the compact event status text shown by the navigation UI."""
    if not getattr(coordinator.config, "enabled", True):
        return ""
    task = coordinator.last_selected_task
    if task is not None and not coordinator._is_event_enabled(task.event_type):
        task = None
    if task is None:
        active = coordinator._enabled_active_tasks()
        if not active:
            return ""
        task = active[0]
    action = describe_action(coordinator.last_action).split(" ", 1)[0] if coordinator.last_action else "idle"
    return (
        f"event:{task.event_type} {task.state.value} "
        f"seen={task.seen_count} act={action}"
    )
