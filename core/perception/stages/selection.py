from __future__ import annotations

from typing import Iterable

import numpy as np

from ..models import TargetDetection


def select_candidate(
    candidates: Iterable[TargetDetection],
    strategy: str = "confidence",
    *,
    reference: tuple[float, float] | None = None,
) -> TargetDetection | None:
    """Select one candidate without performing an action."""
    values = tuple(candidates)
    if not values:
        return None
    normalized = str(strategy or "confidence").strip().lower()
    if normalized == "first":
        return values[0]
    if normalized == "nearest" and reference is not None:
        return min(values, key=lambda item: np.hypot(item.center[0] - reference[0], item.center[1] - reference[1]))
    if normalized in {"confidence", "nearest"}:
        return max(values, key=lambda item: item.confidence)
    raise ValueError(f"unknown candidate selection strategy: {strategy}")
