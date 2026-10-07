"""Local visual recovery adapter with bounded ROI search."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from ..vision.local_roi_matcher import LocalRoiMatcher, RoiMatch


@dataclass(frozen=True, slots=True)
class LocalRecoveryResult:
    valid: bool
    position_native: tuple[float, float] | None
    score: float
    radius: float
    reason: str
    elapsed_ms: float = 0.0


class LocalRecoveryBackend:
    def __init__(self, *, matcher: LocalRoiMatcher | None = None) -> None:
        self.matcher = matcher or LocalRoiMatcher()

    def match(
        self,
        frame: object,
        predicted_position: tuple[float, float],
        search: Callable[[object, tuple[float, float], float], RoiMatch | None],
    ) -> LocalRecoveryResult:
        result = self.matcher.match(frame, predicted_position, search)
        return LocalRecoveryResult(
            result.valid,
            result.position_native,
            result.score,
            result.radius,
            result.reason,
            result.processing_ms,
        )
