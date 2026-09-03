from __future__ import annotations

from core.events.debug import event_log
from core.events.models import EventAction


def wait_result_action(handler, tick, task) -> EventAction:
    elapsed_ms = 0 if handler.last_interact_ms is None else tick.now_ms - handler.last_interact_ms
    if elapsed_ms < int(handler.config.post_interact_wait_ms):
        handler._log_throttled(
            tick,
            "portal waiting post-interact settle",
            id=task.id,
            elapsed_ms=elapsed_ms,
        )
        return EventAction.wait(200, reason="portal waiting post-interact settle")

    completion = handler._teleport_completion(tick)
    if completion is not None:
        event_log(
            "portal teleport completed",
            id=task.id,
            waited_ms=elapsed_ms,
            player=tick.player_global_pos,
            completion=completion,
        )
        return completion_action(task, completion)

    if elapsed_ms >= int(handler.config.teleport_timeout_ms):
        event_log(
            "portal teleport timeout",
            id=task.id,
            timeout_ms=int(handler.config.teleport_timeout_ms),
            player=tick.player_global_pos,
        )
        return EventAction.fail("portal teleport completion timeout")

    handler._log_throttled(
        tick,
        "portal waiting teleport completion",
        id=task.id,
        waited_ms=elapsed_ms,
        player=tick.player_global_pos,
    )
    if not handler.teleport_relocalize_requested:
        handler.teleport_relocalize_requested = True
        event_log(
            "portal request full-map localization",
            id=task.id,
            reason="portal_wait_result",
            waited_ms=elapsed_ms,
            player=tick.player_global_pos,
        )
    return EventAction.wait(
        250,
        reason="portal waiting teleport completion",
        metadata={
            "force_relocalize": True,
            "relocalize_reason": "portal_wait_result",
            "relocalize_score": "event",
        },
    )


def completion_action(task, completion: dict) -> EventAction:
    metadata = {
        "entry_pos": task.global_pos,
        "entry_task_id": task.id,
        "completion_kind": "teleport",
    }
    metadata.update(completion)
    return EventAction.complete("portal teleport completed", metadata=metadata)
