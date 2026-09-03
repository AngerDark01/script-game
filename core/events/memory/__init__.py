from __future__ import annotations

from typing import Iterable

from ..debug import event_log
from ..models import EventObservation, EventTask, EventTaskState
from .completion import (
    complete_teleport_session as complete_teleport_session_impl,
    mark_failed as mark_failed_impl,
    mark_related_completed as mark_related_completed_impl,
    suppress_nearby_pending as suppress_nearby_pending_impl,
)
from .lookup import (
    completed_cooldown_info,
    find_matching_task,
    find_nearest_task,
    find_session_exit_task,
    find_task_by_id,
)
from .merge import merge_event_observations
from .utils import distance, int_pos, should_log


class EventMemory:
    """Tracks event instances across frames.

    It prevents a detector from turning the same icon into a new event every
    frame, keeps events after they leave the minimap view, and suppresses
    recently completed events.
    """

    def __init__(self, dedupe_radius: float = 80.0):
        self.dedupe_radius = float(dedupe_radius)
        self._tasks: list[EventTask] = []
        self._next_id = 1
        self._last_log_ms: dict[str, int] = {}

    def tasks(self) -> list[EventTask]:
        return list(self._tasks)

    def active_tasks(self) -> list[EventTask]:
        return [
            task
            for task in self._tasks
            if task.state in (EventTaskState.PENDING, EventTaskState.RUNNING)
        ]

    def clear_event_type(self, event_type: str, now_ms: int | None = None) -> int:
        before = len(self._tasks)
        self._tasks = [task for task in self._tasks if task.event_type != event_type]
        removed = before - len(self._tasks)
        self._last_log_ms = {
            key: value
            for key, value in self._last_log_ms.items()
            if f":{event_type}" not in key and not key.endswith(event_type)
        }
        event_log(
            "event memory cleared",
            event=event_type,
            removed=removed,
            now_ms=int(now_ms or 0),
        )
        return removed

    def merge_observations(self, observations: Iterable[EventObservation], config, now_ms: int) -> None:
        merge_event_observations(self, observations, config, now_ms)

    def mark_completed(self, task: EventTask, now_ms: int) -> None:
        task.mark_completed(now_ms)
        event_log(
            "task completed",
            id=task.id,
            event=task.event_type,
            attempts=task.attempts,
            global_pos=task.global_pos,
        )

    def complete_teleport_session(
        self,
        entry_task: EventTask,
        exit_pos: tuple[int, int] | None,
        now_ms: int,
        config,
        exit_task_id: str | None = None,
        exit_player_pos: tuple[int, int] | None = None,
    ) -> tuple[EventTask, EventTask | None]:
        return complete_teleport_session_impl(
            self,
            entry_task,
            exit_pos,
            now_ms,
            config,
            exit_task_id=exit_task_id,
            exit_player_pos=exit_player_pos,
        )

    def mark_related_completed(
        self,
        event_type: str,
        global_pos: tuple[int, int] | None,
        now_ms: int,
        config,
        reason: str = "",
    ) -> EventTask | None:
        return mark_related_completed_impl(self, event_type, global_pos, now_ms, config, reason=reason)

    def suppress_nearby_pending(self, completed_task: EventTask, config, now_ms: int) -> None:
        suppress_nearby_pending_impl(self, completed_task, config, now_ms)

    def mark_failed(self, task: EventTask, now_ms: int, config) -> None:
        mark_failed_impl(self, task, now_ms, config)

    def _new_id(self, event_type: str) -> str:
        value = f"{event_type}:{self._next_id}"
        self._next_id += 1
        return value

    def _find_task_by_id(self, task_id: str | None) -> EventTask | None:
        return find_task_by_id(self._tasks, task_id)

    def _find_matching_task(
        self,
        observation: EventObservation,
        event_config: dict | None = None,
        touched_task_ids: set[str] | None = None,
    ) -> EventTask | None:
        return find_matching_task(
            self._tasks,
            observation,
            self.dedupe_radius,
            event_config=event_config,
            touched_task_ids=touched_task_ids,
        )

    def _find_session_exit_task(
        self,
        entry_task: EventTask,
        exit_pos: tuple[int, int] | None,
        event_config: dict | None,
    ) -> EventTask | None:
        return find_session_exit_task(self._tasks, entry_task, exit_pos, event_config, self.dedupe_radius)

    def _find_nearest_task(self, event_type: str, global_pos: tuple[int, int], radius: float) -> EventTask | None:
        return find_nearest_task(self._tasks, event_type, global_pos, radius)

    def _completed_cooldown_info(self, observation: EventObservation, event_config: dict, now_ms: int) -> dict | None:
        return completed_cooldown_info(self._tasks, observation, event_config, now_ms, self.dedupe_radius)

    def _should_log(self, key: str, now_ms: int, interval_ms: int) -> bool:
        return should_log(self._last_log_ms, key, now_ms, interval_ms)


def _distance(a, b) -> float:
    return distance(a, b)


def _int_pos(pos) -> tuple[int, int] | None:
    return int_pos(pos)
