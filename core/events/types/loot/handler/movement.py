from __future__ import annotations

import math

from core.events.models import EventAction


def approach_action(handler, tick, task) -> tuple[EventAction | None, float | None]:
    if tick.player_global_pos is None:
        return EventAction.wait(200, reason="loot waiting for localization"), None

    distance = distance_to_task(task.global_pos, tick.player_global_pos)
    if distance > float(handler.config.arrival_radius):
        handler.state = "move_near_loot"
        return EventAction.move_to(
            task.global_pos,
            reason="move near loot blob",
            metadata={"arrival_radius": float(handler.config.arrival_radius)},
        ), distance

    if distance > float(handler.config.pickup_radius):
        handler.state = "move_pickup_radius"
        return EventAction.move_to(
            task.global_pos,
            reason="approach loot pickup radius",
            metadata={
                "arrival_radius": float(handler.config.pickup_radius),
                "force_repeat_click": True,
            },
        ), distance

    return None, distance


def distance_to_task(target_pos, player_pos) -> float:
    return math.hypot(
        float(target_pos[0]) - float(player_pos[0]),
        float(target_pos[1]) - float(player_pos[1]),
    )
