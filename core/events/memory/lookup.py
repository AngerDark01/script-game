from __future__ import annotations

from ..models import EventObservation, EventTask, EventTaskState
from .utils import distance, int_pos


def find_task_by_id(tasks: list[EventTask], task_id: str | None) -> EventTask | None:
    if not task_id:
        return None
    for task in tasks:
        if str(task.id) == str(task_id):
            return task
    return None


def find_matching_task(
    tasks: list[EventTask],
    observation: EventObservation,
    dedupe_radius: float,
    event_config: dict | None = None,
    touched_task_ids: set[str] | None = None,
) -> EventTask | None:
    if observation.global_pos is None:
        return None
    match_radius = float((event_config or {}).get("dedupe_radius", dedupe_radius))
    for task in tasks:
        if touched_task_ids and task.id in touched_task_ids:
            continue
        if task.event_type != observation.event_type:
            continue
        if task.state in (EventTaskState.COMPLETED, EventTaskState.IGNORED):
            continue
        if distance(task.global_pos, observation.global_pos) <= match_radius:
            return task
    return None


def find_session_exit_task(
    tasks: list[EventTask],
    entry_task: EventTask,
    exit_pos: tuple[int, int] | None,
    event_config: dict | None,
    dedupe_radius: float,
) -> EventTask | None:
    normalized_exit_pos = int_pos(exit_pos)
    if normalized_exit_pos is None:
        return None
    radius = float((event_config or {}).get("exit_complete_radius", (event_config or {}).get("dedupe_radius", dedupe_radius)))
    best = None
    best_distance = None
    for task in tasks:
        if task is entry_task:
            continue
        if task.event_type != entry_task.event_type:
            continue
        if task.state in (EventTaskState.COMPLETED, EventTaskState.IGNORED):
            continue
        task_distance = distance(task.global_pos, normalized_exit_pos)
        if task_distance <= radius and (best_distance is None or task_distance < best_distance):
            best = task
            best_distance = task_distance
    return best


def find_nearest_task(
    tasks: list[EventTask],
    event_type: str,
    global_pos: tuple[int, int],
    radius: float,
) -> EventTask | None:
    best = None
    best_distance = None
    for task in tasks:
        if task.event_type != event_type:
            continue
        if task.state in (EventTaskState.COMPLETED, EventTaskState.IGNORED):
            continue
        task_distance = distance(task.global_pos, global_pos)
        if task_distance <= radius and (best_distance is None or task_distance < best_distance):
            best = task
            best_distance = task_distance
    return best


def completed_cooldown_info(
    tasks: list[EventTask],
    observation: EventObservation,
    event_config: dict,
    now_ms: int,
    dedupe_radius: float,
) -> dict | None:
    cooldown_ms = int(event_config.get("cooldown_ms", 0))
    type_cooldown_ms = int(event_config.get("type_cooldown_ms", 0))
    if observation.global_pos is None:
        return None
    for task in tasks:
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
        cooldown_radius = float(event_config.get("cooldown_radius", dedupe_radius))
        task_distance = distance(task.global_pos, observation.global_pos)
        if task_distance <= cooldown_radius:
            return {
                "matched_task": task.id,
                "matched_state": task.state,
                "cooldown_kind": "position",
                "distance": round(float(task_distance), 2),
                "radius": float(cooldown_radius),
                "remaining_ms": max(0, cooldown_ms - elapsed_ms),
            }
    return None
