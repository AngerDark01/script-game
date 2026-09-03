from __future__ import annotations

from core.events.debug import event_log


def reset_event_type(coordinator, event_type: str, now_ms: int | None = None) -> int:
    """Clear memory, stabilization, runner state, and cached display data for an event type."""
    if (
        coordinator.runner.active_task is not None
        and coordinator.runner.active_task.event_type == event_type
    ):
        coordinator.runner._clear()

    removed_tasks = coordinator.memory.clear_event_type(event_type, now_ms=now_ms)
    removed_clusters = coordinator.position_stabilizer.clear_event_type(event_type, now_ms=now_ms)
    coordinator.last_detections = [
        detection
        for detection in coordinator.last_detections
        if detection.event_type != event_type
    ]
    coordinator.last_observations = [
        observation
        for observation in coordinator.last_observations
        if observation.event_type != event_type
    ]
    if (
        coordinator.last_selected_task is not None
        and coordinator.last_selected_task.event_type == event_type
    ):
        coordinator.last_selected_task = None
    coordinator.last_action = None
    event_log(
        "event coordinator reset event type",
        event=event_type,
        tasks=removed_tasks,
        clusters=removed_clusters,
    )
    return removed_tasks
