from __future__ import annotations

from core.events.hooks import EventHookRegistry

from .coordinate import CoordinateDiagnostics
from .event_approach import EventApproachController
from .models import NavigationIntent
from .movement_executor import MovementExecutor
from .route_context import RouteContext
from .scheduler import NavigationTaskScheduler
from .task_builder import NavigationTaskBuilder
from .update_context import NavigationUpdateContext
from .update_pipeline import update_controller_context
from .static_task_runner import update_static_task
from .event_task_runner import update_event_task
from .controller_runtime import (
    consume_relocalization_intent,
    has_valid_route,
    load_route,
    next_required_index,
    observe_localization,
    record_intent_click,
    reset_runtime,
    start,
    stop,
    update_required_progress,
)
from .controller_utils import (
    float_point,
    int_point,
    is_forced_global_relocalization,
    round_float,
    should_keep_active_task_after_forced_relocalization,
)


class NavigationTaskController:
    """Unified controller for route targets and dynamic event tasks."""

    def __init__(self):
        self.min_confidence = 0.58
        self.max_jump_distance = 160.0
        self.control_alpha = 0.35
        self.arrival_radius = 26.0
        self.required_progress_margin = 36.0
        self.route = None
        self.route_context = RouteContext([])
        self.builder = NavigationTaskBuilder()
        self.scheduler = NavigationTaskScheduler()
        self.movement = MovementExecutor(arrival_radius=self.arrival_radius)
        self.event_approach = EventApproachController()
        self.event_hooks = EventHookRegistry()
        self.coordinate_diagnostics = CoordinateDiagnostics()
        self.active = False
        self.completed_required: set[int] = set()
        self.active_task_id: str | None = None
        self.raw_pos: tuple[float, float] | None = None
        self.trusted_pos: tuple[float, float] | None = None
        self.control_pos: tuple[float, float] | None = None
        self.route_progress: float | None = None
        self.current_intent = NavigationIntent()

    def load_route(self, route: dict | None) -> None:
        load_route(self, route)

    def reset_runtime(self, keep_route: bool = True) -> None:
        reset_runtime(self, keep_route=keep_route)

    def start(self) -> bool:
        return start(self)

    def stop(self) -> None:
        stop(self)

    def has_valid_route(self) -> bool:
        return has_valid_route(self)

    def update_context(self, context: NavigationUpdateContext) -> NavigationIntent:
        return update_controller_context(self, context)

    def observe_localization(self, pos, confidence: float, *, force_snap: bool = False) -> bool:
        return observe_localization(self, pos, confidence, force_snap=force_snap)

    def _consume_relocalization_intent(self, now_ms: int, *, selected=None) -> NavigationIntent | None:
        return consume_relocalization_intent(self, now_ms, selected=selected)

    def _update_required_progress(self) -> None:
        update_required_progress(self)

    def _next_required_index(self, required: list) -> int | None:
        return next_required_index(self, required)

    def _update_static_task(
        self,
        task,
        wall_map,
        pathfinder,
        explored_map,
        now_ms: int,
        lookahead_distance: float,
    ) -> NavigationIntent:
        return update_static_task(
            self,
            task,
            wall_map,
            pathfinder,
            explored_map,
            now_ms,
            lookahead_distance,
        )

    def _update_event_task(
        self,
        task,
        event_coordinator,
        event_tick,
        wall_map,
        pathfinder,
        explored_map,
        now_ms: int,
        lookahead_distance: float,
    ) -> NavigationIntent:
        return update_event_task(
            self,
            task,
            event_coordinator,
            event_tick,
            wall_map,
            pathfinder,
            explored_map,
            now_ms,
            lookahead_distance,
        )

    def record_intent_click(self, intent: NavigationIntent, now_ms: int) -> None:
        record_intent_click(self, intent, now_ms)


def _float_point(point) -> tuple[float, float]:
    return float_point(point)


def _int_point(point) -> tuple[int, int] | None:
    return int_point(point)


def _round_float(value, digits: int = 1):
    return round_float(value, digits)


def _is_forced_global_relocalization(registration, confidence: float, min_confidence: float) -> bool:
    return is_forced_global_relocalization(registration, confidence, min_confidence)


def _should_keep_active_task_after_forced_relocalization(registration, active_task_id: str | None) -> bool:
    return should_keep_active_task_after_forced_relocalization(registration, active_task_id)
