from __future__ import annotations

from ..debug import event_log
from ..models import EventTask, EventTaskState
from .utils import distance, int_pos


def complete_teleport_session(
    memory,
    entry_task: EventTask,
    exit_pos: tuple[int, int] | None,
    now_ms: int,
    config,
    exit_task_id: str | None = None,
    exit_player_pos: tuple[int, int] | None = None,
) -> tuple[EventTask, EventTask | None]:
    event_config = config.event(entry_task.event_type) if hasattr(config, "event") else {}
    session_id = f"teleport:{entry_task.id}:{int(now_ms)}"
    exit_task = memory._find_task_by_id(exit_task_id) if exit_task_id else None
    if exit_task is None:
        exit_task = memory._find_session_exit_task(entry_task, exit_pos, event_config)

    exit_player_pos = int_pos(exit_player_pos) or int_pos(exit_pos)
    normalized_exit_pos = int_pos(exit_pos) or exit_player_pos
    entry_task.metadata["teleport_session_id"] = session_id
    entry_task.metadata["teleport_role"] = "entry"
    if exit_player_pos is not None:
        entry_task.metadata["teleport_exit_player_pos"] = exit_player_pos
    entry_task.mark_completed(now_ms)

    if normalized_exit_pos is not None and exit_task is None:
        exit_task = EventTask(
            id=memory._new_id(entry_task.event_type),
            event_type=entry_task.event_type,
            global_pos=normalized_exit_pos,
            first_seen_ms=int(now_ms),
            last_seen_ms=int(now_ms),
            priority=int(event_config.get("priority", 0)),
            confidence=1.0,
            metadata={"synthetic": True, "complete_reason": "teleport exit"},
        )
        memory._tasks.append(exit_task)

    if exit_task is not None:
        exit_task.last_seen_ms = int(now_ms)
        if normalized_exit_pos is not None:
            exit_task.global_pos = normalized_exit_pos
        exit_task.metadata["teleport_session_id"] = session_id
        exit_task.metadata["teleport_role"] = "exit"
        exit_task.metadata["complete_reason"] = "teleport exit"
        if exit_player_pos is not None:
            exit_task.metadata["teleport_exit_player_pos"] = exit_player_pos
        exit_task.mark_completed(now_ms)

    memory.suppress_nearby_pending(entry_task, config, now_ms)
    if exit_task is not None:
        memory.suppress_nearby_pending(exit_task, config, now_ms)

    event_log(
        "teleport session completed",
        session=session_id,
        entry_id=entry_task.id,
        exit_id=exit_task.id if exit_task is not None else None,
        entry_pos=entry_task.global_pos,
        exit_pos=exit_task.global_pos if exit_task is not None else None,
        exit_player_pos=exit_player_pos,
        exit_task_id=exit_task_id,
    )
    return entry_task, exit_task


def mark_related_completed(
    memory,
    event_type: str,
    global_pos: tuple[int, int] | None,
    now_ms: int,
    config,
    reason: str = "",
) -> EventTask | None:
    if global_pos is None:
        return None
    event_config = config.event(event_type) if hasattr(config, "event") else {}
    radius = float(event_config.get("exit_complete_radius", event_config.get("dedupe_radius", memory.dedupe_radius)))
    task = memory._find_nearest_task(event_type, global_pos, radius)
    if task is None:
        task = EventTask(
            id=memory._new_id(event_type),
            event_type=event_type,
            global_pos=(int(global_pos[0]), int(global_pos[1])),
            first_seen_ms=int(now_ms),
            last_seen_ms=int(now_ms),
            priority=int(event_config.get("priority", 0)),
            confidence=1.0,
            metadata={"synthetic": True, "complete_reason": reason},
        )
        memory._tasks.append(task)
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


def suppress_nearby_pending(memory, completed_task: EventTask, config, now_ms: int) -> None:
    event_config = config.event(completed_task.event_type) if hasattr(config, "event") else {}
    radius = float(event_config.get("cooldown_radius", memory.dedupe_radius))
    for task in memory._tasks:
        if task is completed_task:
            continue
        if task.event_type != completed_task.event_type:
            continue
        if task.state not in (EventTaskState.OBSERVED, EventTaskState.PENDING, EventTaskState.RUNNING):
            continue
        task_distance = distance(task.global_pos, completed_task.global_pos)
        if task_distance > radius:
            continue
        task.last_seen_ms = int(now_ms)
        task.completed_at_ms = int(now_ms)
        task.mark_ignored()
        event_log(
            "nearby task suppressed after completion",
            id=task.id,
            completed_id=completed_task.id,
            event=task.event_type,
            distance=float(task_distance),
            radius=float(radius),
            now_ms=int(now_ms),
        )


def mark_failed(memory, task: EventTask, now_ms: int, config) -> None:
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
