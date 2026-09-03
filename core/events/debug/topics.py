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

    lowered = str(message).lower()
    if "portal" in lowered:
        return "portal"
    if "async event" in lowered:
        return "async"
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
    return _sanitize_topic(text) if text in {"portal", "navigation", "localization", "async"} else None


def _sanitize_topic(value: str) -> str:
    allowed = []
    for char in value.lower():
        if char.isalnum() or char in ("_", "-"):
            allowed.append(char)
        elif char in (":", " ", "."):
            allowed.append("_")
    return "".join(allowed).strip("_")[:48]
