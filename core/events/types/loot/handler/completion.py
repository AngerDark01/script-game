from __future__ import annotations

from core.events.debug import event_log
from core.events.models import EventAction


def wait_result_action(handler, tick, task) -> EventAction:
    if tick.raw_minimap_frame is None:
        return EventAction.wait(200, reason="loot waiting for minimap frame")

    elapsed_ms = 0 if handler.last_pickup_ms is None else int(tick.now_ms) - int(handler.last_pickup_ms)
    if elapsed_ms < int(handler.config.post_pickup_wait_ms):
        return EventAction.wait(200, reason="loot waiting post-pickup settle")

    absence_ms = max(1, int(handler.config.absence_confirm_frames)) * max(1, int(handler.config.absence_frame_ms))
    missing_ms = int(tick.now_ms) - int(task.last_seen_ms)
    if missing_ms >= absence_ms:
        event_log(
            "loot pickup completed absent",
            id=task.id,
            target=task.global_pos,
            missing_ms=missing_ms,
            absence_ms=absence_ms,
            press_count=handler.press_count,
        )
        return EventAction.complete(
            "loot disappeared after pickup",
            metadata={
                "completion_kind": "loot_absent",
                "press_count": int(handler.press_count),
                "missing_ms": int(missing_ms),
                "pickup_radius": int(handler.config.pickup_radius),
            },
        )

    if handler.press_count >= int(handler.config.pickup_press_limit):
        return EventAction.fail("loot still visible after pickup attempts")

    return pickup_repeat_action(handler)


def pickup_repeat_action(handler) -> EventAction:
    handler.state = "move_near_loot"
    return EventAction.wait(120, reason="loot still visible, retry pickup")

