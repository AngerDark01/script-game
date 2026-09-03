"""Event runtime diagnostic logging package."""

from .descriptions import describe_action, describe_task
from .formatting import _format_fields, _format_value
from .topics import _event_topic, _sanitize_topic, _topic_from_value
from .writer import event_log, start_event_log_session
from .writer import _build_line, _new_session_stamp, _write_event_line
from . import writer as _writer

__all__ = [
    "event_log",
    "start_event_log_session",
    "describe_action",
    "describe_task",
    "_format_fields",
    "_format_value",
    "_build_line",
    "_new_session_stamp",
    "_write_event_line",
    "_event_topic",
    "_topic_from_value",
    "_sanitize_topic",
]


def __getattr__(name: str):
    if name in {
        "_EVENT_LOG_PATH",
        "_EVENT_RUN_DIR",
        "_EVENT_SESSION_PID",
        "_EVENT_SESSION_STAMP",
        "_EVENT_SESSION_PATH",
        "_EVENT_STARTED_PATHS",
    }:
        return getattr(_writer, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
