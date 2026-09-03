from __future__ import annotations

from core.events.base.handler import EventHandler
from core.events.debug import event_log
from core.events.models import EventAction

from ..completion_detector import detect_teleport_completion, near_known_exit_portal
from .completion import wait_result_action
from .diagnostics import log_state, log_throttled
from .interaction import interaction_action
from .movement import approach_action


class PortalEventHandler(EventHandler):
    event_type = "portal"

    def __init__(self, config):
        self.config = config
        self.state = "move_near_event"
        self.last_interact_ms = None
        self.interact_pos = None
        self.interact_signature = None
        self.portal_point_click_ms = None
        self.teleport_relocalize_requested = False
        self._last_state = None
        self._last_log_ms = 0

    def start(self, task) -> None:
        super().start(task)
        self._reset_runtime_state()
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
            return wait_result_action(self, tick, task)

        action, distance = approach_action(self, tick, task)
        if action is not None:
            return action
        if distance is None:
            return EventAction.wait(200, reason="portal waiting for localization")
        return interaction_action(self, tick, task, distance)

    def reset(self) -> None:
        super().reset()
        self._reset_runtime_state()

    def _reset_runtime_state(self) -> None:
        self.state = "move_near_event"
        self.last_interact_ms = None
        self.interact_pos = None
        self.interact_signature = None
        self.portal_point_click_ms = None
        self.teleport_relocalize_requested = False
        self._last_state = None
        self._last_log_ms = 0

    def _teleport_completion(self, tick) -> dict | None:
        return detect_teleport_completion(
            config=self.config,
            event_type=self.event_type,
            entry_task=self.task,
            tick=tick,
            interact_pos=self.interact_pos,
            interact_signature=self.interact_signature,
        )

    def _near_known_exit_portal(self, tick):
        return near_known_exit_portal(
            config=self.config,
            event_type=self.event_type,
            entry_task=self.task,
            tick=tick,
        )

    def _log_state(self, task, tick) -> None:
        log_state(self, task, tick)

    def _log_throttled(self, tick, message: str, **fields) -> None:
        log_throttled(self, tick, message, **fields)
