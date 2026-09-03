from __future__ import annotations

from typing import Iterable

from ..debug import event_log
from ..models import EventObservation, EventTask, EventTaskState
from .target_update import should_update_task_target


def merge_event_observations(memory, observations: Iterable[EventObservation], config, now_ms: int) -> None:
    touched_task_ids: set[str] = set()
    for observation in observations:
        event_config = config.event(observation.event_type) if hasattr(config, "event") else {}
        if not event_config.get("enabled", True):
            if memory._should_log(f"disabled:{observation.event_type}", now_ms, 3000):
                event_log(
                    "observation skipped disabled",
                    event=observation.event_type,
                    source=observation.source,
                    conf=float(observation.confidence),
                )
            continue
        cooldown_info = memory._completed_cooldown_info(observation, event_config, now_ms)
        if cooldown_info is not None:
            if memory._should_log(f"cooldown:{observation.event_type}", now_ms, 3000):
                event_log(
                    "observation skipped cooldown",
                    event=observation.event_type,
                    global_pos=observation.global_pos,
                    conf=float(observation.confidence),
                    **cooldown_info,
                )
            continue

        task = memory._find_matching_task(observation, event_config, touched_task_ids=touched_task_ids)
        if task:
            previous_pos = task.global_pos
            update_target, target_update_info = should_update_task_target(task, observation, event_config)
            task.mark_seen(observation, update_global_pos=update_target)
            metadata_update = {
                "last_observed_global_pos": (
                    int(observation.global_pos[0]),
                    int(observation.global_pos[1]),
                ),
                **target_update_info,
            }
            if target_update_info.get("target_locked_global_pos") is None:
                metadata_update.pop("target_locked_global_pos", None)
            if update_target and task.state == EventTaskState.OBSERVED and _uses_locked_target(event_config):
                metadata_update["target_locked_global_pos"] = task.global_pos
            task.metadata.update(metadata_update)
            touched_task_ids.add(task.id)
            if task.seen_count <= 3 or memory._should_log(f"seen:{task.id}", now_ms, 1000):
                event_log(
                    "task seen",
                    id=task.id,
                    event=task.event_type,
                    state=task.state,
                    seen=task.seen_count,
                    conf=float(task.confidence),
                    global_pos=task.global_pos,
                    observed_pos=(
                        int(observation.global_pos[0]),
                        int(observation.global_pos[1]),
                    ),
                    target_updated=bool(update_target),
                    target_drift=round(float(target_update_info.get("target_drift", 0.0)), 2),
                    source=observation.source,
                )
            if not update_target and memory._should_log(f"target_locked:{task.id}", now_ms, 1000):
                event_log(
                    "task target locked",
                    id=task.id,
                    event=task.event_type,
                    state=task.state,
                    global_pos=task.global_pos,
                    observed_pos=(
                        int(observation.global_pos[0]),
                        int(observation.global_pos[1]),
                    ),
                    previous_pos=previous_pos,
                    target_drift=round(float(target_update_info.get("target_drift", 0.0)), 2),
                    reason=str(target_update_info.get("target_update_reason", "")),
                )
        else:
            task = EventTask(
                id=memory._new_id(observation.event_type),
                event_type=observation.event_type,
                global_pos=(int(observation.global_pos[0]), int(observation.global_pos[1])),
                first_seen_ms=int(observation.observed_at_ms),
                last_seen_ms=int(observation.observed_at_ms),
                priority=int(event_config.get("priority", 0)),
                confidence=float(observation.confidence),
                metadata=dict(observation.metadata),
            )
            if _uses_locked_target(event_config):
                task.metadata["target_locked_global_pos"] = task.global_pos
                task.metadata["target_update_mode"] = str(event_config.get("target_update_mode", "continuous"))
                task.metadata["last_observed_global_pos"] = task.global_pos
            memory._tasks.append(task)
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


def _uses_locked_target(event_config: dict | None) -> bool:
    mode = str((event_config or {}).get("target_update_mode", "continuous") or "continuous").strip().lower()
    return mode not in {"", "continuous", "always"}
