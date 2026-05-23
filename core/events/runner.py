from __future__ import annotations

from .debug import describe_action, describe_task, event_log
from .models import EventAction, EventActionType, EventTaskState


class EventRunner:
    def __init__(self, registry, memory):
        self.registry = registry
        self.memory = memory
        self.active_task = None
        self.active_handler = None
        self._last_action_log_ms = 0
        self._last_action_log_key = ""

    def update(self, task, tick, config) -> EventAction | None:
        if task is None:
            if self.active_task is not None:
                event_log("runner idle clear", previous=describe_task(self.active_task))
            self._clear()
            return None

        if self.active_task is not task:
            self._start_task(task, config)

        if self.active_handler is None:
            event_log("runner missing handler", task=describe_task(task))
            return None

        action = self.active_handler.update(tick, task)
        if action is None:
            return None

        if self._should_log_action(action, tick.now_ms):
            event_log("runner action", task=describe_task(task), action=describe_action(action))
        if action.type == EventActionType.COMPLETE:
            exit_pos = (action.metadata or {}).get("exit_pos")
            self.memory.mark_completed(task, tick.now_ms)
            exit_task = None
            if exit_pos is not None:
                exit_task = self.memory.mark_related_completed(
                    task.event_type,
                    exit_pos,
                    tick.now_ms,
                    config,
                    reason="portal exit after teleport",
                )
            self.memory.suppress_nearby_pending(task, config, tick.now_ms)
            if exit_task is not None:
                self.memory.suppress_nearby_pending(exit_task, config, tick.now_ms)
            self._clear()
        elif action.type == EventActionType.FAIL:
            self.memory.mark_failed(task, tick.now_ms, config)
            self._clear()
        return action

    def _start_task(self, task, config) -> None:
        definition = self.registry.get(task.event_type)
        if not definition:
            event_log("runner missing definition", task=describe_task(task))
            return
        if self.active_handler:
            self.active_handler.reset()
        task.mark_running()
        self.active_task = task
        self.active_handler = definition.create_handler(config.event(task.event_type))
        self.active_handler.start(task)
        event_log("runner start task", task=describe_task(task))

    def _clear(self) -> None:
        if self.active_handler:
            self.active_handler.reset()
        self.active_task = None
        self.active_handler = None

    def _should_log_action(self, action: EventAction, now_ms: int) -> bool:
        if action.type in (EventActionType.CLICK_SCREEN, EventActionType.PRESS_KEY, EventActionType.COMPLETE, EventActionType.FAIL):
            return True
        key = describe_action(action)
        if key != self._last_action_log_key or now_ms - self._last_action_log_ms >= 1000:
            self._last_action_log_key = key
            self._last_action_log_ms = int(now_ms)
            return True
        return False
