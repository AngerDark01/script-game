from __future__ import annotations

from core.events.debug import event_log
from core.events.models import EventAction

from ..environment_signature import minimap_environment_signature
from .diagnostics import log_throttled


def interaction_action(handler, tick, task, distance: float) -> EventAction:
    if handler.config.interaction != "key":
        log_throttled(
            handler,
            tick,
            "portal forcing key interaction",
            id=task.id,
            configured_interaction=handler.config.interaction,
        )

    if (
        handler.last_interact_ms is not None
        and tick.now_ms - handler.last_interact_ms < int(handler.config.post_interact_wait_ms)
    ):
        handler.state = "wait_result"
        return EventAction.wait(200, reason="portal interaction cooldown")

    if handler.portal_point_click_ms is None:
        handler.state = "align_on_portal"
        handler.portal_point_click_ms = tick.now_ms
        event_log(
            "portal point click before interaction",
            id=task.id,
            target=task.global_pos,
            player=tick.player_global_pos,
            distance=float(distance),
        )
        return EventAction.move_to(
            task.global_pos,
            reason="click portal map point before interact",
            metadata={
                "force_click_target": True,
                "reason": "portal_point_click_before_interact",
            },
        )

    click_elapsed_ms = tick.now_ms - int(handler.portal_point_click_ms)
    if click_elapsed_ms < int(handler.config.portal_point_click_wait_ms):
        handler.state = "align_on_portal"
        return EventAction.wait(
            min(200, int(handler.config.portal_point_click_wait_ms) - click_elapsed_ms),
            reason="portal waiting after point click",
        )

    if handler.state != "wait_result":
        handler.state = "interact"
        handler.last_interact_ms = tick.now_ms
        handler.interact_pos = tick.player_global_pos
        handler.interact_signature = minimap_environment_signature(
            tick.raw_minimap_frame,
            tick.player_local_minimap_pos,
        )
        handler.state = "wait_result"
        event_log(
            "portal interaction key",
            id=task.id,
            key="d",
            target=task.global_pos,
            player=tick.player_global_pos,
            distance=float(distance),
        )
        return EventAction.press_key("d", reason="interact with portal")
    return EventAction.wait(200, reason="portal waiting interact dispatch")
