from __future__ import annotations

from typing import Any

from core.shared.diagnostics import format_fields, format_value


def _format_fields(fields: dict[str, Any]) -> str:
    return format_fields(fields)


def _format_value(value: Any) -> str:
    return format_value(value)
