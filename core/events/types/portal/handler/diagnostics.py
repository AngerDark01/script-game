from __future__ import annotations

from core.events.debug import event_log


def log_state(handler, task, tick) -> None:
    if handler.state == handler._last_state:
        return
    handler._last_state = handler.state
    event_log("portal state", id=task.id, state=handler.state, now_ms=tick.now_ms)


def log_throttled(handler, tick, message: str, **fields) -> None:
    if tick.now_ms - handler._last_log_ms < 1000:
        return
    handler._last_log_ms = int(tick.now_ms)
    event_log(message, **fields)
