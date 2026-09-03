from __future__ import annotations

from core.events.debug import event_log
from core.events.models import EventAction


def pickup_action(handler, tick, task, distance: float) -> EventAction:
    if handler.press_count >= int(handler.config.pickup_press_limit):
        return EventAction.fail("loot pickup press limit reached")

    handler.state = "wait_result"
    handler.last_pickup_ms = int(tick.now_ms)
    handler.press_count += 1
    event_log(
        "loot pickup key",
        id=task.id,
        key=handler.config.pickup_key,
        target=task.global_pos,
        player=tick.player_global_pos,
        distance=float(distance),
        press_count=handler.press_count,
        pickup_radius=int(handler.config.pickup_radius),
    )
    return EventAction.press_key(handler.config.pickup_key, reason="pick up loot")

