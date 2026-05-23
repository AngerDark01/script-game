from __future__ import annotations

import time
import os
from enum import Enum
from pathlib import Path
from typing import Any

_EVENT_LOG_PATH = Path(__file__).resolve().parents[2] / "logs" / "event_runtime.log"
_EVENT_SESSION_STARTED = False


def event_log(message: str, **fields: Any) -> None:
    """Write one compact event diagnostic to the event file and runtime output."""
    global _EVENT_SESSION_STARTED
    suffix = _format_fields(fields)
    timestamp = time.strftime("%H:%M:%S")
    millis = int((time.time() % 1) * 1000)
    line = f"[Event {timestamp}.{millis:03d} pid={os.getpid()}] {message}{suffix}"
    _EVENT_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    mode = "a" if _EVENT_SESSION_STARTED else "w"
    with _EVENT_LOG_PATH.open(mode, encoding="utf-8") as handle:
        if not _EVENT_SESSION_STARTED:
            handle.write(f"=== event session {time.strftime('%Y-%m-%d %H:%M:%S')} ===\n")
            _EVENT_SESSION_STARTED = True
        handle.write(line + "\n")
    print(line, flush=True)


def describe_action(action) -> str:
    if action is None:
        return "none"
    action_type = _format_value(getattr(action, "type", "unknown"))
    reason = getattr(action, "reason", "") or ""
    target = getattr(action, "target_global_pos", None)
    screen = getattr(action, "screen_pos", None)
    key = getattr(action, "key", None)
    wait_ms = getattr(action, "wait_ms", None)
    parts = [str(action_type)]
    if target is not None:
        parts.append(f"target={_format_value(target)}")
    if screen is not None:
        parts.append(f"screen={_format_value(screen)}")
    if key is not None:
        parts.append(f"key={key}")
    if wait_ms is not None:
        parts.append(f"wait_ms={wait_ms}")
    if reason:
        parts.append(f"reason={reason}")
    return " ".join(parts)


def describe_task(task) -> str:
    if task is None:
        return "none"
    state = _format_value(getattr(task, "state", "unknown"))
    return (
        f"id={getattr(task, 'id', '?')} event={getattr(task, 'event_type', '?')} "
        f"state={state} pos={_format_value(getattr(task, 'global_pos', None))} "
        f"seen={getattr(task, 'seen_count', '?')} attempts={getattr(task, 'attempts', '?')} "
        f"conf={float(getattr(task, 'confidence', 0.0)):.2f}"
    )


def _format_fields(fields: dict[str, Any]) -> str:
    if not fields:
        return ""
    return " | " + " ".join(f"{key}={_format_value(value)}" for key, value in fields.items())


def _format_value(value: Any) -> str:
    if isinstance(value, Enum):
        return str(value.value)
    if isinstance(value, float):
        return f"{value:.2f}"
    if isinstance(value, (tuple, list)):
        return "(" + ",".join(_format_value(item) for item in value) + ")"
    if isinstance(value, dict):
        return "{" + ",".join(f"{key}:{_format_value(val)}" for key, val in value.items()) + "}"
    return str(value)
