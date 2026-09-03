from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any

from .formatting import _format_fields
from .topics import _event_topic, _sanitize_topic

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
_EVENT_LOG_PATH = _PROJECT_ROOT / "logs" / "event_runtime.log"
_EVENT_RUN_DIR = _PROJECT_ROOT / "logs" / "event_runs"
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
    with path.open(mode, encoding="utf-8-sig") as handle:
        if path not in _EVENT_STARTED_PATHS:
            handle.write(
                "=== event session "
                f"{time.strftime('%Y-%m-%d %H:%M:%S')} "
                f"pid={_EVENT_SESSION_PID} file={path.name} ===\n"
            )
            _EVENT_STARTED_PATHS.add(path)
        handle.write(line + "\n")
