from __future__ import annotations

import time
import os
from enum import Enum
from pathlib import Path
from typing import Any

_EVENT_LOG_PATH = Path(__file__).resolve().parents[2] / "logs" / "event_runtime.log"
_EVENT_RUN_DIR = Path(__file__).resolve().parents[2] / "logs" / "event_runs"
_EVENT_SESSION_PID = os.getpid()
_EVENT_SESSION_STAMP = ""
_EVENT_SESSION_PATH = _EVENT_RUN_DIR / f"{_EVENT_SESSION_STAMP}_pid{_EVENT_SESSION_PID}_event_runtime.log"
_EVENT_STARTED_PATHS: set[Path] = set()


def start_event_log_session(label: str = "event") -> Path:
    """Start a new logical event log session without changing caller log format."""
    global _EVENT_SESSION_STAMP, _EVENT_SESSION_PATH
    _EVENT_SESSION_STAMP = _new_session_stamp()
    safe_label = _sanitize_topic(label or "event") or "event"
    _EVENT_SESSION_PATH = _EVENT_RUN_DIR / f"{_EVENT_SESSION_STAMP}_pid{_EVENT_SESSION_PID}_{safe_label}.log"
    _EVENT_STARTED_PATHS.discard(_EVENT_LOG_PATH)
    line = _build_line(
        "event log session started",
        {
            "label": safe_label,
            "archive": _EVENT_SESSION_PATH.name,
        },
    )
    _write_event_line(_EVENT_LOG_PATH, line)
    _write_event_line(_EVENT_SESSION_PATH, line)
    print(line, flush=True)
    return _EVENT_SESSION_PATH


def event_log(message: str, **fields: Any) -> None:
    """Write one compact event diagnostic to the event file and runtime output."""
    global _EVENT_SESSION_STAMP, _EVENT_SESSION_PATH
    if not _EVENT_SESSION_STAMP:
        _EVENT_SESSION_STAMP = _new_session_stamp()
        _EVENT_SESSION_PATH = _EVENT_RUN_DIR / f"{_EVENT_SESSION_STAMP}_pid{_EVENT_SESSION_PID}_event_runtime.log"
    line = _build_line(message, fields)
    _write_event_line(_EVENT_LOG_PATH, line)
    _write_event_line(_EVENT_SESSION_PATH, line)
    topic = _event_topic(message, fields)
    if topic:
        _write_event_line(
            _EVENT_RUN_DIR / f"{_EVENT_SESSION_STAMP}_pid{_EVENT_SESSION_PID}_event_{topic}.log",
            line,
        )
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


def _build_line(message: str, fields: dict[str, Any]) -> str:
    suffix = _format_fields(fields)
    timestamp = time.strftime("%H:%M:%S")
    millis = int((time.time() % 1) * 1000)
    return f"[Event {timestamp}.{millis:03d} pid={os.getpid()}] {message}{suffix}"


def _new_session_stamp() -> str:
    now = time.time()
    return f"{time.strftime('%Y%m%d_%H%M%S', time.localtime(now))}_{int((now % 1) * 1000):03d}"


def _write_event_line(path: Path, line: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    mode = "a" if path in _EVENT_STARTED_PATHS else "w"
    with path.open(mode, encoding="utf-8") as handle:
        if path not in _EVENT_STARTED_PATHS:
            handle.write(
                "=== event session "
                f"{time.strftime('%Y-%m-%d %H:%M:%S')} "
                f"pid={_EVENT_SESSION_PID} file={path.name} ===\n"
            )
            _EVENT_STARTED_PATHS.add(path)
        handle.write(line + "\n")


def _event_topic(message: str, fields: dict[str, Any]) -> str | None:
    explicit = fields.get("event") or fields.get("event_type")
    topic = _topic_from_value(explicit)
    if topic:
        return topic

    for key in ("id", "entry_id", "exit_id", "task", "selected", "previous"):
        topic = _topic_from_value(fields.get(key))
        if topic:
            return topic

    lowered = str(message).lower()
    if "portal" in lowered:
        return "portal"
    if lowered.startswith("nav ") or lowered.startswith("navigation "):
        return "navigation"
    if "localization" in lowered or "relocalization" in lowered:
        return "localization"
    return None


def _topic_from_value(value: Any) -> str | None:
    if value is None:
        return None
    text = _format_value(value).lower()
    if not text:
        return None
    if "event=portal" in text or text.startswith("portal:") or text == "portal":
        return "portal"
    if text.startswith("event:portal"):
        return "portal"
    if text.startswith("required:") or text.startswith("exit:") or text.startswith("nav"):
        return "navigation"
    return _sanitize_topic(text) if text in {"portal", "navigation", "localization"} else None


def _sanitize_topic(value: str) -> str:
    allowed = []
    for char in value.lower():
        if char.isalnum() or char in ("_", "-"):
            allowed.append(char)
        elif char in (":", " ", "."):
            allowed.append("_")
    return "".join(allowed).strip("_")[:48]
