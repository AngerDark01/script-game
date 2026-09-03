from __future__ import annotations

import math
from typing import Any

from core.localization.evidence import (
    float_point_or_none as _evidence_float_point_or_none,
    registration_fields_from_registration,
)
from core.shared.diagnostics import format_fields as _shared_format_fields
from core.shared.diagnostics import format_value as _shared_format_value


def registration_fields(registration) -> dict[str, Any]:
    return registration_fields_from_registration(registration)


def float_point_or_none(point) -> tuple[float, float] | None:
    return _evidence_float_point_or_none(point)


def distance(a: tuple[float, float], b: tuple[float, float]) -> float:
    return math.hypot(float(a[0]) - float(b[0]), float(a[1]) - float(b[1]))


def format_fields(fields: dict[str, Any]) -> str:
    return _shared_format_fields(fields)


def format_value(value: Any) -> str:
    return _shared_format_value(value)
