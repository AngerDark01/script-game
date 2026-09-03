from __future__ import annotations


def float_point(point) -> tuple[float, float]:
    return (float(point[0]), float(point[1]))


def int_point(point) -> tuple[int, int] | None:
    if point is None:
        return None
    return (int(round(float(point[0]))), int(round(float(point[1]))))


def round_float(value, digits: int = 1):
    if value is None:
        return None
    return round(float(value), int(digits))


def is_forced_global_relocalization(registration, confidence: float, min_confidence: float) -> bool:
    if registration is None:
        return False
    metadata = getattr(registration, "metadata", {}) or {}
    return (
        bool(getattr(registration, "valid", False))
        and getattr(registration, "source", "") == "template_match"
        and bool(metadata.get("forced_global"))
        and float(confidence or 0.0) >= float(min_confidence)
    )


def should_keep_active_task_after_forced_relocalization(registration, active_task_id: str | None) -> bool:
    if not active_task_id or not str(active_task_id).startswith("event:"):
        return False
    metadata = getattr(registration, "metadata", {}) or {}
    return str(metadata.get("forced_reason") or "") == "portal_wait_result"
