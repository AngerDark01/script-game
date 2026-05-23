from __future__ import annotations

from .debug import describe_action, event_log
from .models import EventActionType


class EventActionExecutor:
    def __init__(self, move_to_callback=None, click_screen_callback=None, press_key_callback=None):
        self.move_to_callback = move_to_callback
        self.click_screen_callback = click_screen_callback
        self.press_key_callback = press_key_callback
        self.last_result = None
        self._last_log_ms_by_key = {}

    def execute(self, action) -> bool:
        if action is None or action.type == EventActionType.NONE:
            self.last_result = "none"
            return False
        self._log_execute("execute action", action)
        if action.type == EventActionType.MOVE_TO:
            if self.move_to_callback:
                self.move_to_callback(action.target_global_pos, action.metadata)
            self.last_result = "move_to"
            self._log_execute("execute result", action, result=self.last_result)
            return True
        if action.type == EventActionType.CLICK_SCREEN:
            if self.click_screen_callback:
                self.click_screen_callback(action.screen_pos)
            self.last_result = "click_screen"
            self._log_execute("execute result", action, result=self.last_result)
            return True
        if action.type == EventActionType.PRESS_KEY:
            if self.press_key_callback:
                self.press_key_callback(action.key)
            self.last_result = "press_key"
            self._log_execute("execute result", action, result=self.last_result)
            return True
        if action.type in (EventActionType.WAIT, EventActionType.COMPLETE, EventActionType.FAIL):
            self.last_result = action.type.value
            self._log_execute("execute result", action, result=self.last_result)
            return True
        self.last_result = "unknown"
        self._log_execute("execute result", action, result=self.last_result)
        return False

    def _log_execute(self, message: str, action, **fields) -> None:
        if action.type in (EventActionType.CLICK_SCREEN, EventActionType.PRESS_KEY, EventActionType.COMPLETE, EventActionType.FAIL):
            event_log(message, action=describe_action(action), **fields)
            return
        import time

        now_ms = time.monotonic() * 1000.0
        key = f"{message}:{describe_action(action)}"
        last_ms = self._last_log_ms_by_key.get(key, 0.0)
        if now_ms - last_ms >= 1000:
            self._last_log_ms_by_key[key] = now_ms
            event_log(message, action=describe_action(action), **fields)
