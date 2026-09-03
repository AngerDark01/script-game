from __future__ import annotations

from core.events.base.handler import EventHandler
from core.events.debug import event_log
from core.events.models import EventAction

from .completion import wait_result_action
from .interaction import pickup_action
from .movement import approach_action


class LootPickupHandler(EventHandler):
    event_type = "loot"

    def __init__(self, config):
        self.config = config
        self.state = "move_near_loot"
        self.last_pickup_ms = None
        self.press_count = 0

    def start(self, task) -> None:
        super().start(task)
        self._reset_runtime_state()
        event_log(
            "loot handler start",
            id=task.id,
            target=task.global_pos,
            arrival_radius=int(self.config.arrival_radius),
            pickup_radius=int(self.config.pickup_radius),
            pickup_key=self.config.pickup_key,
        )

    def update(self, tick, task):
        if self.state == "wait_result":
            return wait_result_action(self, tick, task)

        action, distance = approach_action(self, tick, task)
        if action is not None:
            return action
        if distance is None:
            return EventAction.wait(200, reason="loot waiting for localization")
        return pickup_action(self, tick, task, distance)

    def reset(self) -> None:
        super().reset()
        self._reset_runtime_state()

    def _reset_runtime_state(self) -> None:
        self.state = "move_near_loot"
        self.last_pickup_ms = None
        self.press_count = 0
