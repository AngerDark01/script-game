from __future__ import annotations

import math

import cv2
import numpy as np

from core.events.base.handler import EventHandler
from core.events.debug import event_log
from core.events.models import EventAction


class PortalEventHandler(EventHandler):
    event_type = "portal"

    def __init__(self, config):
        self.config = config
        self.state = "move_near_event"
        self.last_interact_ms = None
        self.interact_pos = None
        self.interact_signature = None
        self._last_state = None
        self._last_log_ms = 0

    def start(self, task) -> None:
        super().start(task)
        self.state = "move_near_event"
        self.last_interact_ms = None
        self.interact_pos = None
        self.interact_signature = None
        self._last_state = None
        self._last_log_ms = 0
        event_log(
            "portal handler start",
            id=task.id,
            target=task.global_pos,
            arrival_radius=int(self.config.arrival_radius),
            interaction=self.config.interaction,
        )

    def update(self, tick, task):
        self._log_state(task, tick)
        if self.state == "wait_result":
            elapsed_ms = 0 if self.last_interact_ms is None else tick.now_ms - self.last_interact_ms
            if elapsed_ms < int(self.config.post_interact_wait_ms):
                self._log_throttled(
                    tick,
                    "portal waiting post-interact settle",
                    id=task.id,
                    elapsed_ms=elapsed_ms,
                )
                return EventAction.wait(200, reason="portal waiting post-interact settle")

            if self._teleport_completed(tick):
                event_log(
                    "portal teleport completed",
                    id=task.id,
                    waited_ms=elapsed_ms,
                    player=tick.player_global_pos,
                )
                metadata = {"entry_pos": task.global_pos}
                if tick.player_global_pos is not None:
                    metadata["exit_pos"] = (
                        int(tick.player_global_pos[0]),
                        int(tick.player_global_pos[1]),
                    )
                return EventAction.complete("portal teleport completed", metadata=metadata)

            if elapsed_ms >= int(self.config.teleport_timeout_ms):
                event_log(
                    "portal teleport timeout",
                    id=task.id,
                    timeout_ms=int(self.config.teleport_timeout_ms),
                    player=tick.player_global_pos,
                )
                return EventAction.fail("portal teleport completion timeout")

            self._log_throttled(
                tick,
                "portal waiting teleport completion",
                id=task.id,
                waited_ms=elapsed_ms,
                player=tick.player_global_pos,
            )
            return EventAction.wait(250, reason="portal waiting teleport completion")

        if tick.player_global_pos is None:
            self._log_throttled(tick, "portal waiting localization", id=task.id)
            return EventAction.wait(200, reason="portal waiting for localization")

        distance = math.hypot(
            float(task.global_pos[0]) - float(tick.player_global_pos[0]),
            float(task.global_pos[1]) - float(tick.player_global_pos[1]),
        )
        if distance > float(self.config.arrival_radius):
            self.state = "move_near_event"
            self._log_throttled(
                tick,
                "portal move near",
                id=task.id,
                distance=float(distance),
                target=task.global_pos,
                player=tick.player_global_pos,
            )
            return EventAction.move_to(task.global_pos, reason="move near portal")

        if distance > float(self.config.interact_radius):
            self.state = "move_near_event"
            self._log_throttled(
                tick,
                "portal approach final radius",
                id=task.id,
                distance=float(distance),
                interact_radius=int(self.config.interact_radius),
                target=task.global_pos,
                player=tick.player_global_pos,
            )
            return EventAction.move_to(task.global_pos, reason="approach portal interact radius")

        if self.config.interaction != "key":
            self._log_throttled(
                tick,
                "portal forcing key interaction",
                id=task.id,
                configured_interaction=self.config.interaction,
            )

        if self.last_interact_ms is not None and tick.now_ms - self.last_interact_ms < int(self.config.post_interact_wait_ms):
            self.state = "wait_result"
            return EventAction.wait(200, reason="portal interaction cooldown")

        if self.state != "wait_result":
            self.state = "interact"
            self.last_interact_ms = tick.now_ms
            self.interact_pos = tick.player_global_pos
            self.interact_signature = _minimap_environment_signature(tick.raw_minimap_frame, tick.player_local_minimap_pos)
            self.state = "wait_result"
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

    def reset(self) -> None:
        super().reset()
        self.state = "move_near_event"
        self.last_interact_ms = None
        self.interact_pos = None
        self.interact_signature = None
        self._last_state = None
        self._last_log_ms = 0

    def _teleport_completed(self, tick) -> bool:
        if self.interact_pos is not None and tick.player_global_pos is not None:
            distance = math.hypot(
                float(tick.player_global_pos[0]) - float(self.interact_pos[0]),
                float(tick.player_global_pos[1]) - float(self.interact_pos[1]),
            )
            if distance >= float(self.config.teleport_min_distance):
                event_log(
                    "portal teleport position changed",
                    distance=float(distance),
                    threshold=int(self.config.teleport_min_distance),
                )
                return True

        current_signature = _minimap_environment_signature(tick.raw_minimap_frame, tick.player_local_minimap_pos)
        if self.interact_signature is not None and current_signature is not None:
            diff = _signature_difference(self.interact_signature, current_signature)
            if diff >= float(self.config.environment_change_threshold):
                event_log(
                    "portal teleport environment changed",
                    diff=float(diff),
                    threshold=float(self.config.environment_change_threshold),
                )
                return True
        return False

    def _log_state(self, task, tick) -> None:
        if self.state == self._last_state:
            return
        self._last_state = self.state
        event_log("portal state", id=task.id, state=self.state, now_ms=tick.now_ms)

    def _log_throttled(self, tick, message: str, **fields) -> None:
        if tick.now_ms - self._last_log_ms < 1000:
            return
        self._last_log_ms = int(tick.now_ms)
        event_log(message, **fields)


def _minimap_environment_signature(frame, player_pos) -> np.ndarray | None:
    if frame is None:
        return None
    if player_pos is None:
        center_x = frame.shape[1] // 2
        center_y = frame.shape[0] // 2
    else:
        center_x = int(player_pos[0])
        center_y = int(player_pos[1])
    half = 46
    left = max(0, center_x - half)
    right = min(frame.shape[1], center_x + half)
    top = max(0, center_y - half)
    bottom = min(frame.shape[0], center_y + half)
    patch = frame[top:bottom, left:right]
    if patch.size == 0:
        return None
    gray = cv2.cvtColor(patch, cv2.COLOR_BGR2GRAY) if patch.ndim == 3 else patch
    gray = cv2.resize(gray, (32, 32), interpolation=cv2.INTER_AREA)
    return gray.astype(np.float32) / 255.0


def _signature_difference(before: np.ndarray, after: np.ndarray) -> float:
    if before.shape != after.shape:
        return 1.0
    return float(np.mean(np.abs(before - after)))
