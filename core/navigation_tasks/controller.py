from __future__ import annotations

import copy

from core.events.models import EventActionType
from core.path_utils import is_inside_exit_region, point_distance

from .debug import nav_log
from .models import NavigationIntent, NavigationIntentType, NavigationTaskKind
from .movement_executor import MovementExecutor
from .route_context import RouteContext
from .scheduler import NavigationTaskScheduler
from .task_builder import NavigationTaskBuilder


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
        self.active = False
        self.completed_required: set[int] = set()
        self.active_task_id: str | None = None
        self.raw_pos: tuple[float, float] | None = None
        self.trusted_pos: tuple[float, float] | None = None
        self.control_pos: tuple[float, float] | None = None
        self.route_progress: float | None = None
        self.current_intent = NavigationIntent()

    def load_route(self, route: dict | None) -> None:
        self.route = copy.deepcopy(route) if route else None
        self.route_context = RouteContext((self.route or {}).get("guide_points", []))
        self.reset_runtime(keep_route=True)

    def reset_runtime(self, keep_route: bool = True) -> None:
        if not keep_route:
            self.route = None
            self.route_context = RouteContext([])
        self.active = False
        self.completed_required = set()
        self.active_task_id = None
        self.raw_pos = None
        self.trusted_pos = None
        self.control_pos = None
        self.route_progress = None
        self.current_intent = NavigationIntent()
        self.movement.reset()

    def start(self) -> bool:
        if not self.has_valid_route():
            return False
        self.active = True
        self.movement.reset()
        nav_log("nav task controller started")
        return True

    def stop(self) -> None:
        self.active = False
        self.active_task_id = None
        self.current_intent = NavigationIntent()
        self.movement.reset()
        nav_log("nav task controller stopped")

    def has_valid_route(self) -> bool:
        return bool(self.route and self.route.get("exit_region"))

    def update(
        self,
        *,
        localized_pos,
        confidence: float,
        route: dict | None,
        event_coordinator,
        event_tick,
        wall_map,
        pathfinder,
        explored_map,
        now_ms: int,
        lookahead_distance: float,
        manual_event_only: bool = False,
    ) -> NavigationIntent:
        if route is not None and route != self.route:
            self.load_route(route)
            self.active = True
        if not self.active:
            self.current_intent = NavigationIntent(message="navigation task controller inactive")
            return self.current_intent
        if not self.observe_localization(localized_pos, confidence):
            self.current_intent = NavigationIntent(
                type=NavigationIntentType.WAIT,
                message="waiting localization",
            )
            return self.current_intent

        self._update_required_progress()
        event_tasks = event_coordinator.tasks() if event_coordinator else []
        tasks = self.builder.build(
            route=self.route,
            event_tasks=event_tasks,
            route_context=self.route_context,
            completed_required=self.completed_required,
        )
        selected = self.scheduler.pick(
            tasks=tasks,
            player_pos=self.control_pos,
            route_context=self.route_context,
            active_task_id=self.active_task_id,
            manual_event_only=manual_event_only,
        )
        if selected is None:
            self.current_intent = NavigationIntent(
                type=NavigationIntentType.WAIT,
                player_pos=self.control_pos,
                message="no navigation task selected",
            )
            return self.current_intent

        if selected.id != self.active_task_id:
            player_progress = self.route_context.progress_of(self.control_pos) if self.control_pos is not None else None
            nav_log(
                "nav task transition",
                previous=self.active_task_id,
                selected=selected.id,
                kind=selected.kind.value,
                target=_int_point(selected.target_pos),
                player=_int_point(self.control_pos),
                player_progress=_round_float(player_progress),
                target_progress=_round_float(selected.route_progress),
                completed_required=",".join(str(index) for index in sorted(self.completed_required)),
            )
            self.active_task_id = selected.id
            self.movement.reset()

        if selected.kind == NavigationTaskKind.EVENT:
            self.current_intent = self._update_event_task(
                selected,
                event_coordinator,
                event_tick,
                wall_map,
                pathfinder,
                explored_map,
                now_ms,
                lookahead_distance,
            )
            return self.current_intent

        self.current_intent = self._update_static_task(
            selected,
            wall_map,
            pathfinder,
            explored_map,
            now_ms,
            lookahead_distance,
        )
        return self.current_intent

    def observe_localization(self, pos, confidence: float) -> bool:
        self.raw_pos = _float_point(pos) if pos is not None else None
        if pos is None or float(confidence or 0.0) < self.min_confidence:
            return False

        candidate = _float_point(pos)
        if self.trusted_pos is not None:
            jump = point_distance(candidate, self.trusted_pos)
            if jump > self.max_jump_distance and float(confidence or 0.0) < 0.9:
                nav_log("nav localization rejected jump", jump=round(float(jump), 2), confidence=float(confidence or 0.0))
                return False

        self.trusted_pos = candidate
        if self.control_pos is None:
            self.control_pos = candidate
        else:
            alpha = 0.5 if float(confidence or 0.0) >= 0.9 else self.control_alpha
            self.control_pos = (
                self.control_pos[0] + (candidate[0] - self.control_pos[0]) * alpha,
                self.control_pos[1] + (candidate[1] - self.control_pos[1]) * alpha,
            )
        projection = self.route_context.project(self.control_pos)
        if projection is not None:
            self.route_progress = projection.progress if self.route_progress is None else max(self.route_progress, projection.progress)
        return True

    def _update_required_progress(self) -> None:
        if self.control_pos is None or not self.route:
            return
        required = self.route.get("required_points", []) or []
        if not required:
            return
        projection = self.route_context.project(self.control_pos)
        player_progress = projection.progress if projection else None
        next_index = self._next_required_index(required)
        if next_index is None:
            return

        target = _float_point(required[next_index])
        distance = point_distance(self.control_pos, target)
        reached_by_distance = distance <= self.arrival_radius
        target_progress = self.route_context.progress_of(target)
        progress_delta = None
        if player_progress is not None and target_progress is not None:
            progress_delta = float(player_progress) - float(target_progress)

        if reached_by_distance:
            self.completed_required.add(next_index)
            nav_log(
                "nav required completed",
                index=next_index,
                target=_int_point(target),
                player=_int_point(self.control_pos),
                by_distance=True,
                by_progress=False,
                distance=round(float(distance), 2),
                player_progress=_round_float(player_progress),
                target_progress=_round_float(target_progress),
                progress_delta=_round_float(progress_delta),
            )
            self.movement.reset()
            self.active_task_id = None

    def _next_required_index(self, required: list) -> int | None:
        for index in range(len(required)):
            if index not in self.completed_required:
                return index
        return None

    def _update_static_task(
        self,
        task,
        wall_map,
        pathfinder,
        explored_map,
        now_ms: int,
        lookahead_distance: float,
    ) -> NavigationIntent:
        if self.control_pos is None:
            return NavigationIntent(type=NavigationIntentType.WAIT, task_id=task.id, message="waiting localization")

        if task.kind == NavigationTaskKind.EXIT and is_inside_exit_region(self.control_pos, task.metadata.get("exit_region")):
            self.active = False
            nav_log("nav task arrived exit", task=task.id, player=_int_point(self.control_pos))
            return NavigationIntent(
                type=NavigationIntentType.ARRIVED,
                task_id=task.id,
                task_kind=task.kind.value,
                player_pos=self.control_pos,
                target_pos=task.target_pos,
                message="arrived exit",
            )

        if task.kind == NavigationTaskKind.REQUIRED and task.required_index is not None:
            if point_distance(self.control_pos, task.target_pos) <= self.arrival_radius:
                self.completed_required.add(int(task.required_index))
                self.active_task_id = None
                self.movement.reset()
                nav_log("nav task reached required", task=task.id, player=_int_point(self.control_pos))
                return NavigationIntent(
                    type=NavigationIntentType.WAIT,
                    task_id=task.id,
                    task_kind=task.kind.value,
                    player_pos=self.control_pos,
                    target_pos=task.target_pos,
                    required_index=task.required_index,
                    message="required reached",
                )

        step = self.movement.step(
            task_id=task.id,
            current_pos=self.control_pos,
            target_pos=task.target_pos,
            wall_map=wall_map,
            pathfinder=pathfinder,
            explored_map=explored_map,
            now_ms=now_ms,
            lookahead_distance=lookahead_distance,
            route_context=self.route_context,
        )
        if step is None:
            return NavigationIntent(
                type=NavigationIntentType.WAIT,
                task_id=task.id,
                task_kind=task.kind.value,
                player_pos=self.control_pos,
                target_pos=task.target_pos,
                message="path unavailable",
            )
        intent_type = NavigationIntentType.MOVE_MAP if step.should_click and step.subgoal else NavigationIntentType.WAIT
        return NavigationIntent(
            type=intent_type,
            task_id=task.id,
            task_kind=task.kind.value,
            player_pos=self.control_pos,
            target_pos=task.target_pos,
            subgoal=step.subgoal,
            path=step.path,
            path_kind=step.path_kind,
            required_index=task.required_index,
            message="move static task" if intent_type == NavigationIntentType.MOVE_MAP else "hold static task",
            metadata={"deviation": step.deviation},
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
        if event_coordinator is None or event_tick is None:
            return NavigationIntent(type=NavigationIntentType.WAIT, task_id=task.id, task_kind=task.kind.value, message="event context unavailable")

        event_task_id = str(task.metadata.get("event_task_id") or "")
        action = event_coordinator.run_task(event_task_id, event_tick)
        if action is None or action.type == EventActionType.NONE:
            return NavigationIntent(
                type=NavigationIntentType.WAIT,
                task_id=task.id,
                task_kind=task.kind.value,
                player_pos=self.control_pos,
                target_pos=task.target_pos,
                message="event idle",
            )

        if action.type == EventActionType.MOVE_TO:
            target = _float_point(action.target_global_pos)
            if action.metadata.get("force_click_target"):
                return NavigationIntent(
                    type=NavigationIntentType.MOVE_MAP,
                    task_id=task.id,
                    task_kind=task.kind.value,
                    player_pos=self.control_pos,
                    target_pos=target,
                    subgoal=target,
                    path=[self.control_pos, target] if self.control_pos else [],
                    path_kind="forced_target",
                    message=action.reason or "event forced target click",
                    metadata={"force_click_target": True, "event_action": action},
                )
            step = self.movement.step(
                task_id=task.id,
                current_pos=self.control_pos,
                target_pos=target,
                wall_map=wall_map,
                pathfinder=pathfinder,
                explored_map=explored_map,
                now_ms=now_ms,
                lookahead_distance=lookahead_distance,
                route_context=self.route_context,
                force_repeat_click=bool(action.metadata.get("force_repeat_click", False)),
            )
            if step is None:
                return NavigationIntent(
                    type=NavigationIntentType.WAIT,
                    task_id=task.id,
                    task_kind=task.kind.value,
                    player_pos=self.control_pos,
                    target_pos=target,
                    message="event path unavailable",
                    metadata={"event_action": action},
                )
            intent_type = NavigationIntentType.MOVE_MAP if step.should_click and step.subgoal else NavigationIntentType.WAIT
            return NavigationIntent(
                type=intent_type,
                task_id=task.id,
                task_kind=task.kind.value,
                player_pos=self.control_pos,
                target_pos=target,
                subgoal=step.subgoal,
                path=step.path,
                path_kind=step.path_kind,
                message=action.reason or "event move",
                metadata={"event_action": action, "deviation": step.deviation},
            )

        if action.type == EventActionType.CLICK_SCREEN:
            return NavigationIntent(
                type=NavigationIntentType.CLICK_SCREEN,
                task_id=task.id,
                task_kind=task.kind.value,
                player_pos=self.control_pos,
                target_pos=task.target_pos,
                message=action.reason or "event click screen",
                metadata={"event_action": action, "screen_pos": action.screen_pos},
            )
        if action.type == EventActionType.PRESS_KEY:
            return NavigationIntent(
                type=NavigationIntentType.PRESS_KEY,
                task_id=task.id,
                task_kind=task.kind.value,
                player_pos=self.control_pos,
                target_pos=task.target_pos,
                message=action.reason or "event press key",
                metadata={"event_action": action, "key": action.key},
            )
        if action.type == EventActionType.WAIT:
            return NavigationIntent(
                type=NavigationIntentType.WAIT,
                task_id=task.id,
                task_kind=task.kind.value,
                player_pos=self.control_pos,
                target_pos=task.target_pos,
                message=action.reason or "event wait",
                metadata={"event_action": action, "wait_ms": action.wait_ms},
            )
        if action.type == EventActionType.COMPLETE:
            nav_log("nav event task completed", task=task.id, event=task.event_type)
            self.active_task_id = None
            self.movement.reset()
            return NavigationIntent(
                type=NavigationIntentType.WAIT,
                task_id=task.id,
                task_kind=task.kind.value,
                player_pos=self.control_pos,
                target_pos=task.target_pos,
                message=action.reason or "event completed",
                metadata={"event_action": action, "terminal": True},
            )
        if action.type == EventActionType.FAIL:
            nav_log("nav event task failed", task=task.id, event=task.event_type, reason=action.reason)
            self.active_task_id = None
            self.movement.reset()
            return NavigationIntent(
                type=NavigationIntentType.WAIT,
                task_id=task.id,
                task_kind=task.kind.value,
                player_pos=self.control_pos,
                target_pos=task.target_pos,
                message=action.reason or "event failed",
                metadata={"event_action": action, "terminal": True},
            )

        return NavigationIntent(type=NavigationIntentType.WAIT, task_id=task.id, task_kind=task.kind.value, message="event action ignored")

    def record_intent_click(self, intent: NavigationIntent, now_ms: int) -> None:
        if intent.subgoal is None:
            return
        self.movement.record_click(now_ms=int(now_ms), subgoal=intent.subgoal)


def _float_point(point) -> tuple[float, float]:
    return (float(point[0]), float(point[1]))


def _int_point(point) -> tuple[int, int] | None:
    if point is None:
        return None
    return (int(round(float(point[0]))), int(round(float(point[1]))))


def _round_float(value, digits: int = 1):
    if value is None:
        return None
    return round(float(value), int(digits))
