from __future__ import annotations

import copy

from core.navigation_tasks.debug import nav_log
from core.navigation_tasks.models import NavigationIntent
from core.navigation_tasks.route_context import RouteContext


def load_route(controller, route: dict | None) -> None:
    controller.route = copy.deepcopy(route) if route else None
    controller.route_context = RouteContext((controller.route or {}).get("guide_points", []))
    controller.reset_runtime(keep_route=True)


def reset_runtime(controller, keep_route: bool = True) -> None:
    if not keep_route:
        controller.route = None
        controller.route_context = RouteContext([])
    controller.active = False
    controller.completed_required = set()
    controller.active_task_id = None
    controller.raw_pos = None
    controller.trusted_pos = None
    controller.control_pos = None
    controller.route_progress = None
    controller.current_intent = NavigationIntent()
    controller.movement.reset()
    controller.event_approach.reset()
    controller.coordinate_diagnostics.reset()


def start(controller) -> bool:
    if not controller.has_valid_route():
        return False
    controller.active = True
    controller.movement.reset()
    controller.event_approach.reset()
    controller.coordinate_diagnostics.record_session_start()
    nav_log("nav task controller started")
    return True


def stop(controller) -> None:
    controller.active = False
    controller.active_task_id = None
    controller.current_intent = NavigationIntent()
    controller.movement.reset()
    controller.event_approach.reset()
    nav_log("nav task controller stopped")


def has_valid_route(controller) -> bool:
    return bool(controller.route and controller.route.get("exit_region"))


def record_intent_click(controller, intent: NavigationIntent, now_ms: int) -> None:
    if intent.subgoal is None:
        return
    controller.movement.record_click(now_ms=int(now_ms), subgoal=intent.subgoal)
