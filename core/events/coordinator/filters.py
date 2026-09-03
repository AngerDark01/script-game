from __future__ import annotations


def should_log(coordinator, now_ms: int, interval_ms: int) -> bool:
    """Throttle coordinator-level event logs."""
    if now_ms - coordinator._last_log_ms < interval_ms:
        return False
    coordinator._last_log_ms = int(now_ms)
    return True


def is_event_enabled(coordinator, event_type: str) -> bool:
    """Return whether a concrete event type is enabled in current config."""
    event_config = coordinator.config.event(event_type) if hasattr(coordinator.config, "event") else {}
    return bool(event_config.get("enabled", True))


def enabled_active_tasks(coordinator) -> list:
    """Return active memory tasks whose event type is enabled."""
    tasks = []
    for task in coordinator.memory.active_tasks():
        if is_event_enabled(coordinator, task.event_type):
            tasks.append(task)
    return tasks


def enabled_display_tasks(coordinator) -> list:
    """Return all displayable memory tasks whose event type is enabled."""
    tasks = []
    for task in coordinator.memory.tasks():
        if is_event_enabled(coordinator, task.event_type):
            tasks.append(task)
    return tasks
