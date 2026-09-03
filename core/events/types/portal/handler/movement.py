from __future__ import annotations

import math

from core.events.models import EventAction

from .diagnostics import log_throttled


def approach_action(handler, tick, task) -> tuple[EventAction | None, float | None]:
    if tick.player_global_pos is None:
        log_throttled(handler, tick, "portal waiting localization", id=task.id)
        return EventAction.wait(200, reason="portal waiting for localization"), None

    distance = distance_to_task(task.global_pos, tick.player_global_pos)
    if distance > float(handler.config.arrival_radius):
        handler.state = "move_near_event"
        log_throttled(
            handler,
            tick,
            "portal move near",
            id=task.id,
            distance=float(distance),
            target=task.global_pos,
            player=tick.player_global_pos,
        )
        return EventAction.move_to(
            task.global_pos,
            reason="move near portal",
            metadata={"arrival_radius": float(handler.config.arrival_radius)},
        ), distance

    if distance > float(handler.config.interact_radius):
        handler.state = "move_near_event"
        log_throttled(
            handler,
            tick,
            "portal approach final radius",
            id=task.id,
            distance=float(distance),
            interact_radius=int(handler.config.interact_radius),
            target=task.global_pos,
            player=tick.player_global_pos,
        )
        return EventAction.move_to(
            task.global_pos,
            reason="approach portal interact radius",
            metadata={
                "arrival_radius": float(handler.config.interact_radius),
                "force_repeat_click": True,
            },
        ), distance

    return None, distance


def distance_to_task(target_pos, player_pos) -> float:
    return math.hypot(
        float(target_pos[0]) - float(player_pos[0]),
        float(target_pos[1]) - float(player_pos[1]),
    )
