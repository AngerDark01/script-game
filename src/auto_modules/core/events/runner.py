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
            self._clear(requeue_running=True)
            return None

        if task.state in (EventTaskState.COMPLETED, EventTaskState.IGNORED):
            event_log("runner terminal task ignored", task=describe_task(task))
            if self.active_task is task:
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
            metadata = action.metadata or {}
            if metadata.get("completion_kind") == "teleport":
                self.memory.complete_teleport_session(
                    task,
                    exit_pos=metadata.get("exit_pos"),
                    exit_task_id=metadata.get("exit_task_id"),
                    exit_player_pos=metadata.get("exit_player_pos"),
                    now_ms=tick.now_ms,
                    config=config,
                )
            else:
                self.memory.mark_completed(task, tick.now_ms)
                self.memory.suppress_nearby_pending(task, config, tick.now_ms)
            self._clear()
        elif action.type == EventActionType.FAIL:
            self.memory.mark_failed(task, tick.now_ms, config)
            self._clear()
        return action

    def _start_task(self, task, config) -> None:
        if task.state in (EventTaskState.COMPLETED, EventTaskState.IGNORED):
            event_log("runner refused terminal task", task=describe_task(task))
            return
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

    def _clear(self, requeue_running: bool = False) -> None:
        if requeue_running and self.active_task is not None:
            state_value = getattr(getattr(self.active_task, "state", None), "value", getattr(self.active_task, "state", None))
            if str(state_value).lower() == "running":
                self.active_task.state = EventTaskState.PENDING
                event_log("runner requeued active task", task=describe_task(self.active_task))
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
