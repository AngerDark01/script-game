from __future__ import annotations

import math
from typing import Iterable

from .debug import event_log
from .models import EventObservation, EventTask, EventTaskState


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

    def merge_observations(self, observations: Iterable[EventObservation], config, now_ms: int) -> None:
        touched_task_ids: set[str] = set()
        for observation in observations:
            event_config = config.event(observation.event_type) if hasattr(config, "event") else {}
            if not event_config.get("enabled", True):
                if self._should_log(f"disabled:{observation.event_type}", now_ms, 3000):
                    event_log(
                        "observation skipped disabled",
                        event=observation.event_type,
                        source=observation.source,
                        conf=float(observation.confidence),
                    )
                continue
            cooldown_info = self._completed_cooldown_info(observation, event_config, now_ms)
            if cooldown_info is not None:
                if self._should_log(f"cooldown:{observation.event_type}", now_ms, 3000):
                    event_log(
                        "observation skipped cooldown",
                        event=observation.event_type,
                        global_pos=observation.global_pos,
                        conf=float(observation.confidence),
                        **cooldown_info,
                    )
                continue

            task = self._find_matching_task(observation, event_config, touched_task_ids=touched_task_ids)
            if task:
                task.mark_seen(observation)
                touched_task_ids.add(task.id)
                if task.seen_count <= 3 or self._should_log(f"seen:{task.id}", now_ms, 1000):
                    event_log(
                        "task seen",
                        id=task.id,
                        event=task.event_type,
                        state=task.state,
                        seen=task.seen_count,
                        conf=float(task.confidence),
                        global_pos=task.global_pos,
                        source=observation.source,
                    )
            else:
                task = EventTask(
                    id=self._new_id(observation.event_type),
                    event_type=observation.event_type,
                    global_pos=(int(observation.global_pos[0]), int(observation.global_pos[1])),
                    first_seen_ms=int(observation.observed_at_ms),
                    last_seen_ms=int(observation.observed_at_ms),
                    priority=int(event_config.get("priority", 0)),
                    confidence=float(observation.confidence),
                    metadata=dict(observation.metadata),
                )
                self._tasks.append(task)
                touched_task_ids.add(task.id)
                event_log(
                    "task created",
                    id=task.id,
                    event=task.event_type,
                    state=task.state,
                    seen=task.seen_count,
                    conf=float(task.confidence),
                    global_pos=task.global_pos,
                    source=observation.source,
                )

            confirm_frames = max(1, int(event_config.get("memory_confirm_frames", 1)))
            previous_state = task.state
            if task.seen_count >= confirm_frames:
                task.mark_pending()
                if previous_state != task.state:
                    event_log(
                        "task confirmed pending",
                        id=task.id,
                        event=task.event_type,
                        seen=task.seen_count,
                        confirm_frames=confirm_frames,
                        global_pos=task.global_pos,
                    )
            elif task.state == EventTaskState.OBSERVED:
                event_log(
                    "task waiting confirm",
                    id=task.id,
                    event=task.event_type,
                    seen=task.seen_count,
                    confirm_frames=confirm_frames,
                )

    def mark_completed(self, task: EventTask, now_ms: int) -> None:
        task.mark_completed(now_ms)
        event_log(
            "task completed",
            id=task.id,
            event=task.event_type,
            attempts=task.attempts,
            global_pos=task.global_pos,
        )

    def mark_related_completed(
        self,
        event_type: str,
        global_pos: tuple[int, int] | None,
        now_ms: int,
        config,
        reason: str = "",
    ) -> EventTask | None:
        if global_pos is None:
            return None
        event_config = config.event(event_type) if hasattr(config, "event") else {}
        radius = float(event_config.get("exit_complete_radius", event_config.get("dedupe_radius", self.dedupe_radius)))
        task = self._find_nearest_task(event_type, global_pos, radius)
        if task is None:
            task = EventTask(
                id=self._new_id(event_type),
                event_type=event_type,
                global_pos=(int(global_pos[0]), int(global_pos[1])),
                first_seen_ms=int(now_ms),
                last_seen_ms=int(now_ms),
                priority=int(event_config.get("priority", 0)),
                confidence=1.0,
                metadata={"synthetic": True, "complete_reason": reason},
            )
            self._tasks.append(task)
        else:
            task.global_pos = (int(global_pos[0]), int(global_pos[1]))
            task.last_seen_ms = int(now_ms)
            task.metadata["complete_reason"] = reason
        task.mark_completed(now_ms)
        event_log(
            "related task completed",
            id=task.id,
            event=task.event_type,
            reason=reason,
            global_pos=task.global_pos,
            radius=float(radius),
        )
        return task

    def suppress_nearby_pending(self, completed_task: EventTask, config, now_ms: int) -> None:
        event_config = config.event(completed_task.event_type) if hasattr(config, "event") else {}
        radius = float(event_config.get("cooldown_radius", self.dedupe_radius))
        for task in self._tasks:
            if task is completed_task:
                continue
            if task.event_type != completed_task.event_type:
                continue
            if task.state not in (EventTaskState.OBSERVED, EventTaskState.PENDING, EventTaskState.RUNNING):
                continue
            distance = _distance(task.global_pos, completed_task.global_pos)
            if distance > radius:
                continue
            task.last_seen_ms = int(now_ms)
            task.completed_at_ms = int(now_ms)
            task.mark_ignored()
            event_log(
                "nearby task suppressed after completion",
                id=task.id,
                completed_id=completed_task.id,
                event=task.event_type,
                distance=float(distance),
                radius=float(radius),
                now_ms=int(now_ms),
            )

    def mark_failed(self, task: EventTask, now_ms: int, config) -> None:
        task.mark_failed(now_ms)
        event_config = config.event(task.event_type) if hasattr(config, "event") else {}
        retry_limit = int(event_config.get("retry_limit", 0))
        if task.attempts >= retry_limit:
            task.last_seen_ms = int(now_ms)
            task.completed_at_ms = int(now_ms)
            task.mark_ignored()
            event_log(
                "task failed ignored",
                id=task.id,
                event=task.event_type,
                attempts=task.attempts,
                retry_limit=retry_limit,
                global_pos=task.global_pos,
            )
        else:
            task.state = EventTaskState.PENDING
            event_log(
                "task failed retry",
                id=task.id,
                event=task.event_type,
                attempts=task.attempts,
                retry_limit=retry_limit,
                global_pos=task.global_pos,
            )

    def _new_id(self, event_type: str) -> str:
        value = f"{event_type}:{self._next_id}"
        self._next_id += 1
        return value

    def _find_matching_task(
        self,
        observation: EventObservation,
        event_config: dict | None = None,
        touched_task_ids: set[str] | None = None,
    ) -> EventTask | None:
        if observation.global_pos is None:
            return None
        match_radius = float((event_config or {}).get("dedupe_radius", self.dedupe_radius))
        for task in self._tasks:
            if touched_task_ids and task.id in touched_task_ids:
                continue
            if task.event_type != observation.event_type:
                continue
            if task.state in (EventTaskState.COMPLETED, EventTaskState.IGNORED):
                continue
            if _distance(task.global_pos, observation.global_pos) <= match_radius:
                return task
        return None

    def _find_nearest_task(self, event_type: str, global_pos: tuple[int, int], radius: float) -> EventTask | None:
        best = None
        best_distance = None
        for task in self._tasks:
            if task.event_type != event_type:
                continue
            if task.state in (EventTaskState.COMPLETED, EventTaskState.IGNORED):
                continue
            distance = _distance(task.global_pos, global_pos)
            if distance <= radius and (best_distance is None or distance < best_distance):
                best = task
                best_distance = distance
        return best

    def _completed_cooldown_info(self, observation: EventObservation, event_config: dict, now_ms: int) -> dict | None:
        cooldown_ms = int(event_config.get("cooldown_ms", 0))
        type_cooldown_ms = int(event_config.get("type_cooldown_ms", 0))
        if observation.global_pos is None:
            return None
        for task in self._tasks:
            if task.event_type != observation.event_type:
                continue
            completed_at_ms = task.completed_at_ms
            if completed_at_ms is None and task.state == EventTaskState.IGNORED:
                completed_at_ms = task.last_seen_ms
            if completed_at_ms is None:
                continue
            elapsed_ms = now_ms - int(completed_at_ms)
            if type_cooldown_ms > 0 and elapsed_ms <= type_cooldown_ms:
                return {
                    "matched_task": task.id,
                    "matched_state": task.state,
                    "cooldown_kind": "type",
                    "remaining_ms": max(0, type_cooldown_ms - elapsed_ms),
                }
            if cooldown_ms <= 0 or elapsed_ms > cooldown_ms:
                continue
            cooldown_radius = float(event_config.get("cooldown_radius", self.dedupe_radius))
            distance = _distance(task.global_pos, observation.global_pos)
            if distance <= cooldown_radius:
                return {
                    "matched_task": task.id,
                    "matched_state": task.state,
                    "cooldown_kind": "position",
                    "distance": round(float(distance), 2),
                    "radius": float(cooldown_radius),
                    "remaining_ms": max(0, cooldown_ms - elapsed_ms),
                }
        return None

    def _should_log(self, key: str, now_ms: int, interval_ms: int) -> bool:
        last_ms = self._last_log_ms.get(key)
        if last_ms is not None and now_ms - last_ms < interval_ms:
            return False
        self._last_log_ms[key] = int(now_ms)
        return True


def _distance(a, b) -> float:
    return float(math.hypot(float(a[0]) - float(b[0]), float(a[1]) - float(b[1])))
