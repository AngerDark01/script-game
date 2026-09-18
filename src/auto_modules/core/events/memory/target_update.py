from __future__ import annotations

from ..models import EventObservation, EventTask, EventTaskState
from .utils import distance, int_pos


def should_update_task_target(
    task: EventTask,
    observation: EventObservation,
    event_config: dict | None,
) -> tuple[bool, dict]:
    config = event_config or {}
    mode = str(config.get("target_update_mode", "continuous") or "continuous").strip().lower()
    current_pos = int_pos(getattr(task, "global_pos", None))
    next_pos = int_pos(getattr(observation, "global_pos", None))
    if current_pos is None or next_pos is None:
        return True, {"target_update_mode": mode, "target_update_reason": "missing_position"}

    drift = distance(current_pos, next_pos)
    if mode in {"continuous", "always", ""}:
        return True, {"target_update_mode": mode or "continuous", "target_drift": float(drift)}
    if mode in {"locked", "never"}:
        return False, {"target_update_mode": mode, "target_drift": float(drift), "target_update_reason": "locked"}
    if mode in {"lock_after_confirm", "lock_after_pending"}:
        if task.state == EventTaskState.OBSERVED:
            return True, {"target_update_mode": mode, "target_drift": float(drift), "target_update_reason": "observed"}
        locked_pos = int_pos((getattr(task, "metadata", {}) or {}).get("target_locked_global_pos")) or current_pos
        return False, {
            "target_update_mode": mode,
            "target_drift": float(drift),
            "target_locked_global_pos": locked_pos,
            "target_update_reason": "locked_after_confirm",
        }
    if mode == "limited_after_confirm":
        if task.state == EventTaskState.OBSERVED:
            return True, {"target_update_mode": mode, "target_drift": float(drift), "target_update_reason": "observed"}
        locked_pos = int_pos((getattr(task, "metadata", {}) or {}).get("target_locked_global_pos")) or current_pos
        locked_drift = distance(locked_pos, next_pos)
        max_drift = float(config.get("target_update_max_drift", 0.0) or 0.0)
        if max_drift > 0 and locked_drift <= max_drift:
            return True, {
                "target_update_mode": mode,
                "target_drift": float(drift),
                "target_locked_drift": float(locked_drift),
                "target_locked_global_pos": locked_pos,
                "target_update_reason": "within_locked_drift",
            }
        return False, {
            "target_update_mode": mode,
            "target_drift": float(drift),
            "target_locked_drift": float(locked_drift),
            "target_locked_global_pos": locked_pos,
            "target_update_reason": "outside_locked_drift",
        }
    return True, {"target_update_mode": "continuous", "target_drift": float(drift), "target_update_reason": "unknown_mode"}
