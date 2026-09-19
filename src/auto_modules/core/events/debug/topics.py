from __future__ import annotations

from typing import Any

from .formatting import _format_value


def _event_topic(message: str, fields: dict[str, Any]) -> str | None:
    explicit = fields.get("event") or fields.get("event_type")
    topic = _topic_from_value(explicit)
    if topic:
        return topic

    for key in ("id", "entry_id", "exit_id", "task", "selected", "previous"):
        topic = _topic_from_value(fields.get(key))
        if topic:
            return topic

    lowered = str(message).lower().strip()
    if "async event" in lowered:
        return "async"
    if lowered.startswith("nav ") or lowered.startswith("navigation "):
        return "navigation"
    if "localization" in lowered or "relocalization" in lowered:
        return "localization"
    # Feature log messages conventionally begin with their event type. Derive
    # the topic without teaching the generic logger any concrete event names.
    first_word = lowered.split(maxsplit=1)[0].rstrip(":") if lowered else ""
    return _sanitize_topic(first_word) or None


def _topic_from_value(value: Any) -> str | None:
    if value is None:
        return None
    text = _format_value(value).lower()
    if not text:
        return None
    if text.startswith("required:") or text.startswith("exit:") or text.startswith("nav"):
        return "navigation"
    if text.startswith("event="):
        return _sanitize_topic(text.removeprefix("event=").split()[0]) or None
    if text.startswith("event:"):
        return _sanitize_topic(text.removeprefix("event:").split(":", 1)[0]) or None
    if ":" in text:
        return _sanitize_topic(text.split(":", 1)[0]) or None
    return _sanitize_topic(text) if text in {"navigation", "localization", "async"} else None


def _sanitize_topic(value: str) -> str:
    allowed = []
    for char in value.lower():
        if char.isalnum() or char in ("_", "-"):
            allowed.append(char)
        elif char in (":", " ", "."):
            allowed.append("_")
    return "".join(allowed).strip("_")[:48]
