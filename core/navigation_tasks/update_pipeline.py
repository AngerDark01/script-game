from __future__ import annotations

from core.navigation_tasks.controller_utils import (
    int_point,
    is_forced_global_relocalization,
    round_float,
    should_keep_active_task_after_forced_relocalization,
)
from core.navigation_tasks.debug import nav_log
from core.navigation_tasks.models import NavigationIntent, NavigationIntentType, NavigationTaskKind


def update_controller_context(controller, context) -> NavigationIntent:
    """Run NavigationTaskController.update_context without keeping the pipeline in the facade."""
    localized_pos = context.localization.pos
    confidence = context.localization.confidence
    route = context.route
    event_coordinator = context.events.coordinator
    event_tick = context.events.tick
    wall_map = context.planning.wall_map
    pathfinder = context.planning.pathfinder
    explored_map = context.planning.explored_map
    now_ms = context.now_ms
    lookahead_distance = context.planning.lookahead_distance
    manual_event_only = context.events.manual_event_only
    frame_registration = context.localization.frame_registration

    if route is not None and route != controller.route:
        controller.load_route(route)
        controller.active = True
    if not controller.active:
        controller.current_intent = NavigationIntent(message="navigation task controller inactive")
        return controller.current_intent

    force_snap = is_forced_global_relocalization(frame_registration, confidence, controller.min_confidence)
    localization_ok = controller.observe_localization(localized_pos, confidence, force_snap=force_snap)
    controller.coordinate_diagnostics.record_localization(
        now_ms=now_ms,
        raw_pos=controller.raw_pos,
        confidence=confidence,
        min_confidence=controller.min_confidence,
        registration=frame_registration,
        trusted_pos=controller.trusted_pos,
        control_pos=controller.control_pos,
        active_task_id=controller.active_task_id,
    )
    if not localization_ok:
        controller.current_intent = NavigationIntent(
            type=NavigationIntentType.WAIT,
            message="waiting localization",
        )
        return controller.current_intent

    if force_snap:
        keep_active_task = should_keep_active_task_after_forced_relocalization(
            frame_registration,
            controller.active_task_id,
        )
        controller.coordinate_diagnostics.mark_relocalization_accepted(
            now_ms=now_ms,
            pos=controller.control_pos,
            confidence=confidence,
            registration=frame_registration,
        )
        controller.movement.reset()
        if not keep_active_task:
            controller.active_task_id = None
        nav_log(
            "nav coordinate relocalization accepted",
            player=int_point(controller.control_pos),
            confidence=round(float(confidence or 0.0), 2),
            keep_active_task=bool(keep_active_task),
            active_task=controller.active_task_id,
        )

    recovery_intent = controller._consume_relocalization_intent(now_ms)
    if recovery_intent is not None:
        controller.current_intent = recovery_intent
        return controller.current_intent

    controller._update_required_progress()
    event_tasks = event_coordinator.tasks() if event_coordinator else []
    tasks = controller.builder.build(
        route=controller.route,
        event_tasks=event_tasks,
        route_context=controller.route_context,
        completed_required=controller.completed_required,
    )
    selected = controller.scheduler.pick(
        tasks=tasks,
        player_pos=controller.control_pos,
        route_context=controller.route_context,
        active_task_id=controller.active_task_id,
        manual_event_only=manual_event_only,
    )
    if selected is None:
        controller.current_intent = NavigationIntent(
            type=NavigationIntentType.WAIT,
            player_pos=controller.control_pos,
            message="no navigation task selected",
        )
        return controller.current_intent

    controller.coordinate_diagnostics.record_navigation_state(
        now_ms=now_ms,
        task_id=selected.id,
        task_kind=selected.kind.value,
        target_pos=selected.target_pos,
        raw_pos=controller.raw_pos,
        trusted_pos=controller.trusted_pos,
        control_pos=controller.control_pos,
        confidence=confidence,
        route_context=controller.route_context,
        arrival_radius=selected.radius or controller.arrival_radius,
        registration=frame_registration,
    )
    recovery_intent = controller._consume_relocalization_intent(now_ms, selected=selected)
    if recovery_intent is not None:
        controller.current_intent = recovery_intent
        return controller.current_intent

    if selected.id != controller.active_task_id:
        player_progress = (
            controller.route_context.progress_of(controller.control_pos)
            if controller.control_pos is not None
            else None
        )
        nav_log(
            "nav task transition",
            previous=controller.active_task_id,
            selected=selected.id,
            kind=selected.kind.value,
            target=int_point(selected.target_pos),
            player=int_point(controller.control_pos),
            player_progress=round_float(player_progress),
            target_progress=round_float(selected.route_progress),
            completed_required=",".join(str(index) for index in sorted(controller.completed_required)),
        )
        controller.active_task_id = selected.id
        controller.movement.reset()
        if selected.kind != NavigationTaskKind.EVENT:
            controller.event_approach.reset_active()

    if selected.kind == NavigationTaskKind.EVENT:
        controller.current_intent = controller._update_event_task(
            selected,
            event_coordinator,
            event_tick,
            wall_map,
            pathfinder,
            explored_map,
            now_ms,
            lookahead_distance,
        )
        return controller.current_intent

    controller.current_intent = controller._update_static_task(
        selected,
        wall_map,
        pathfinder,
        explored_map,
        now_ms,
        lookahead_distance,
    )
    return controller.current_intent
