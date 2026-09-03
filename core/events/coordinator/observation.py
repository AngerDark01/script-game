from __future__ import annotations

from core.events.debug import describe_task, event_log


def observe_events(coordinator, tick) -> None:
    """Detect, stabilize, merge, and select event tasks for one frame."""
    if not getattr(coordinator.config, "enabled", True):
        handle_disabled_observation(coordinator, tick)
        return

    detections = detect_events(coordinator, tick)
    apply_event_detections(coordinator, tick, detections)


def detect_events(coordinator, tick) -> list:
    """Run raw event detectors for one tick."""
    if not getattr(coordinator.config, "enabled", True):
        return []
    return coordinator.monitor.detect(tick, coordinator.config)


def apply_event_detections(coordinator, tick, detections) -> None:
    """Stabilize, merge, and select event tasks from raw detector output."""
    coordinator.last_detections = detections
    observations = coordinator.position_stabilizer.update(
        detections,
        getattr(tick, "frame_registration", None),
        coordinator.config,
        tick.now_ms,
    )
    coordinator.last_observations = observations
    log_detection_summary(coordinator, tick.now_ms, detections)
    log_observation_summary(coordinator, tick.now_ms, observations)

    coordinator.memory.merge_observations(observations, coordinator.config, tick.now_ms)
    tick.event_tasks = coordinator.memory.tasks()
    active_tasks = coordinator._enabled_active_tasks()
    display_task = coordinator.scheduler.pick(active_tasks, tick.player_global_pos)
    if display_task is not coordinator.last_selected_task:
        event_log("scheduler selected", task=describe_task(display_task))
        coordinator.last_selected_task = display_task


def handle_disabled_observation(coordinator, tick) -> None:
    """Stop active runner work and clear display state when events are disabled."""
    if coordinator._should_log(tick.now_ms, 3000):
        event_log("coordinator disabled")
    if coordinator.runner.active_task is not None:
        coordinator.runner.update(None, tick, coordinator.config)
    coordinator.last_action = None
    coordinator.last_selected_task = None


def log_detection_summary(coordinator, now_ms: int, detections) -> None:
    """Throttle and log raw detector output."""
    if detections and coordinator._should_log(now_ms, 750):
        event_log(
            "event detections",
            count=len(detections),
            best=max(float(item.confidence) for item in detections),
            events=",".join(sorted({item.event_type for item in detections})),
        )


def log_observation_summary(coordinator, now_ms: int, observations) -> None:
    """Throttle and log stable localized observations."""
    if observations and coordinator._should_log(now_ms, 750):
        event_log(
            "stable observations",
            count=len(observations),
            best=max(float(item.confidence) for item in observations),
            events=",".join(sorted({item.event_type for item in observations})),
        )
