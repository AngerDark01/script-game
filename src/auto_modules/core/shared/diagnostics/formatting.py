from __future__ import annotations

from enum import Enum
from typing import Any


def format_fields(fields: dict[str, Any]) -> str:
    if not fields:
        return ""
    return " | " + " ".join(f"{key}={format_value(value)}" for key, value in fields.items())


def format_value(value: Any) -> str:
    if isinstance(value, Enum):
        return str(value.value)
    if isinstance(value, float):
        return f"{value:.2f}"
    if isinstance(value, (tuple, list)):
        return "(" + ",".join(format_value(item) for item in value) + ")"
    if isinstance(value, dict):
        return "{" + ",".join(f"{key}:{format_value(val)}" for key, val in value.items()) + "}"
    return str(value)
