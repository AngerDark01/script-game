from __future__ import annotations

from ..debug import nav_log
from .geometry import (
    approach_target_from_path,
    approach_target_from_path_with_stop_radius,
    float_point_or_none,
    int_point_or_none,
    is_event_in_real_view,
)
from .models import EventApproachConfig, EventApproachResult
from .motion import move_toward_event
from .pipeline import update_event_approach
from .settle import reset_settle, settle_or_ready


class EventApproachController:
    """Navigation-layer gate before an event handler is allowed to trigger."""

    def __init__(self):
        self.config = EventApproachConfig()
        self._task_id: str | None = None
        self._released: set[str] = set()
        self._phase = "idle"
        self._last_player_pos: tuple[float, float] | None = None
        self._stable_frames = 0
        self._settle_started_ms: int | None = None
        self._last_log_ms = 0
        self._visible_hook_tasks: set[str] = set()

    def configure(self, **kwargs) -> None:
        values = self.config.__dict__.copy()
        values.update(kwargs)
        self.config = EventApproachConfig(**values)

    def reset(self) -> None:
        self._task_id = None
        self._released.clear()
        self._phase = "idle"
        self._last_player_pos = None
        self._stable_frames = 0
        self._settle_started_ms = None
        self._last_log_ms = 0
        self._visible_hook_tasks.clear()

    def reset_active(self) -> None:
        self._task_id = None
        self._phase = "idle"
        self._last_player_pos = None
        self._stable_frames = 0
        self._settle_started_ms = None
        self._last_log_ms = 0

    def finish_task(self, task_id: str | None) -> None:
        if task_id:
            self._released.discard(str(task_id))
            self._visible_hook_tasks.discard(str(task_id))
        if self._task_id == task_id:
            self.reset_active()

    def is_released(self, task_id: str | None) -> bool:
        return bool(task_id and str(task_id) in self._released)

    def release_task(self, task_id: str | None) -> None:
        if not task_id:
            return
        self._released.add(str(task_id))
        self.reset_active()

    def update(
        self,
        *,
        task,
        current_pos,
        wall_map,
        pathfinder,
        explored_map,
        now_ms: int,
        lookahead_distance: float,
        route_context,
        movement,
    ) -> EventApproachResult:
        return update_event_approach(
            self,
            task=task,
            current_pos=current_pos,
            wall_map=wall_map,
            pathfinder=pathfinder,
            explored_map=explored_map,
            now_ms=now_ms,
            lookahead_distance=lookahead_distance,
            route_context=route_context,
            movement=movement,
        )

    def _move_toward_event(
        self,
        *,
        task,
        current,
        target,
        wall_map,
        pathfinder,
        explored_map,
        now_ms: int,
        lookahead_distance: float,
        route_context,
        movement,
        phase: str,
        click_cooldown_ms: int | None,
        goal_stop_radius: float | None = None,
    ) -> EventApproachResult:
        return move_toward_event(
            self,
            task=task,
            current=current,
            target=target,
            wall_map=wall_map,
            pathfinder=pathfinder,
            explored_map=explored_map,
            now_ms=now_ms,
            lookahead_distance=lookahead_distance,
            route_context=route_context,
            movement=movement,
            phase=phase,
            click_cooldown_ms=click_cooldown_ms,
            goal_stop_radius=goal_stop_radius,
        )

    def _settle_or_ready(
        self,
        *,
        task,
        current,
        target,
        approach_target,
        now_ms: int,
        distance: float,
    ) -> EventApproachResult:
        return settle_or_ready(
            self,
            task=task,
            current=current,
            target=target,
            approach_target=approach_target,
            now_ms=now_ms,
            distance=distance,
        )

    def _is_event_in_real_view(self, player, target) -> bool:
        return is_event_in_real_view(self.config, player, target)

    def _approach_target_from_path(self, path, target) -> tuple[float, float] | None:
        return approach_target_from_path(self.config, path, target)

    def _approach_target_from_path_with_stop_radius(self, path, target, stop_radius: float) -> tuple[float, float] | None:
        return approach_target_from_path_with_stop_radius(self.config, path, target, stop_radius)

    def _reset_settle(self) -> None:
        reset_settle(self)

    def _mark_visible_target(self, task_id: str | None) -> bool:
        if not task_id:
            return False
        key = str(task_id)
        if key in self._visible_hook_tasks:
            return False
        self._visible_hook_tasks.add(key)
        return True

    def _log_phase(self, now_ms: int, phase: str, **fields) -> None:
        if phase == self._phase and int(now_ms) - self._last_log_ms < 1000:
            return
        self._phase = phase
        self._last_log_ms = int(now_ms)
        nav_log(f"event approach {phase}", **fields)


def _float_point(point) -> tuple[float, float] | None:
    return float_point_or_none(point)


def _int_point(point) -> tuple[int, int] | None:
    return int_point_or_none(point)
