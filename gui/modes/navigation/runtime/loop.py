from __future__ import annotations

import time

from core.events.debug import event_log
from core.navigation_tasks.update_context import (
    EventRuntimeSnapshot,
    LocalizationSnapshot,
    NavigationUpdateContext,
    PlanningSnapshot,
)

_LAST_ASYNC_APPLY_LOG_MS = 0


def resolve_player_local_position(
    *,
    nav_config,
    nav_core,
    tracker,
    frame,
    capture_rect: dict,
    default_player_pos,
    previous_player_local_pos,
):
    """Resolve the player position inside the current capture frame."""
    if nav_config.monitor_region:
        player_mask = nav_core.recognizer.extract_player(frame)
        player_pos = tracker.detect_player(player_mask) if tracker else None
        if player_pos is None:
            player_pos = previous_player_local_pos or (
                capture_rect["width"] // 2,
                capture_rect["height"] // 2,
            )
        return player_pos
    return default_player_pos


def update_navigation_task_controller(
    *,
    navigation_task_controller,
    localization,
    route_data,
    event_coordinator,
    event_tick,
    nav_core,
    path_finder,
    now_ms: int,
    lookahead_distance: float,
    manual_event_only: bool,
):
    """Call the navigation task controller with the current frame context."""
    main_route = (route_data or {}).get("routes", {}).get("main", {})
    context = NavigationUpdateContext(
        now_ms=int(now_ms),
        localization=LocalizationSnapshot(
            pos=localization.localized_pos,
            confidence=float(localization.confidence or 0.0),
            frame_registration=getattr(nav_core, "last_frame_registration", None),
        ),
        route=main_route,
        planning=PlanningSnapshot(
            wall_map=nav_core.nav_wall_layer,
            pathfinder=path_finder,
            explored_map=nav_core.explored_map,
            lookahead_distance=float(lookahead_distance or 0.0),
        ),
        events=EventRuntimeSnapshot(
            coordinator=event_coordinator,
            tick=event_tick,
            manual_event_only=bool(manual_event_only),
        ),
    )
    return navigation_task_controller.update_context(context)


def observe_navigation_events(
    *,
    event_coordinator,
    event_observer=None,
    build_event_tick,
    render_event_overlay,
    event_dialog,
    now_ms: int,
    frame,
    player_pos,
    localized_pos,
    confidence: float,
):
    """Run event observation for the current navigation frame and return the tick."""
    if not event_coordinator:
        return None

    event_tick = build_event_tick(
        now_ms,
        frame,
        player_pos,
        localized_pos,
        confidence,
    )
    if not getattr(event_coordinator.config, "enabled", True):
        if event_observer is not None and hasattr(event_observer, "discard_pending_and_result"):
            event_observer.discard_pending_and_result("event coordinator disabled")
        event_coordinator.observe(event_tick)
    elif event_observer is None:
        event_coordinator.observe(event_tick)
    else:
        result = event_observer.poll(max_age_ms=2000)
        if result is not None and not result.error:
            apply_start = time.perf_counter()
            apply_cpu_start = _thread_cpu_time()
            event_coordinator.apply_detections(result.tick, result.detections)
            apply_ms = (time.perf_counter() - apply_start) * 1000.0
            apply_cpu_ms = (_thread_cpu_time() - apply_cpu_start) * 1000.0
            _log_async_apply(
                now_ms=now_ms,
                result=result,
                apply_ms=apply_ms,
                apply_cpu_ms=apply_cpu_ms,
                task_count=len(event_coordinator.tasks()),
            )
        event_tick.event_tasks = event_coordinator.tasks()
        event_observer.submit(event_tick, event_coordinator.config)

    render_event_overlay()
    if event_dialog and event_dialog.isVisible():
        event_dialog.refresh_tasks()
    return event_tick


def _log_async_apply(*, now_ms: int, result, apply_ms: float, apply_cpu_ms: float, task_count: int) -> None:
    global _LAST_ASYNC_APPLY_LOG_MS
    if apply_ms < 20.0 and now_ms - _LAST_ASYNC_APPLY_LOG_MS < 1000:
        return
    _LAST_ASYNC_APPLY_LOG_MS = int(now_ms)
    event_log(
        "async event detections applied",
        seq=getattr(result, "sequence", 0),
        detections=len(getattr(result, "detections", []) or []),
        apply_ms=round(float(apply_ms), 2),
        apply_cpu_ms=round(float(apply_cpu_ms), 2),
        detect_ms=round(float(getattr(result, "detect_ms", 0.0) or 0.0), 2),
        detect_cpu_ms=round(float(getattr(result, "detect_cpu_ms", 0.0) or 0.0), 2),
        queue_ms=round(float(getattr(result, "queue_ms", 0.0) or 0.0), 2),
        result_age_ms=result.age_ms() if hasattr(result, "age_ms") else 0,
        tasks=int(task_count),
    )


def _thread_cpu_time() -> float:
    clock = getattr(time, "thread_time", None) or time.process_time
    return float(clock())
