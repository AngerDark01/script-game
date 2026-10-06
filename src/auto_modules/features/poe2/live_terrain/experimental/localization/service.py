"""Common estimate and relocalization boundary used by experiments."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any, Protocol


@dataclass(frozen=True, slots=True)
class PositionEstimate:
    position: tuple[float, float] | None
    source: str
    confidence: float
    captured_at_ms: int | None = None
    map_instance_id: str | None = None
    fresh: bool = False
    diagnostics: dict[str, Any] | None = None


class Relocalizer(Protocol):
    def locate(self, context: Any) -> PositionEstimate: ...


class RelocalizationService:
    def __init__(self, relocalizer: Relocalizer) -> None:
        self.relocalizer = relocalizer
        self.last_estimate: PositionEstimate | None = None

    def locate(self, context: Any) -> PositionEstimate:
        estimate = self.relocalizer.locate(context)
        self.last_estimate = estimate
        return estimate

    def invalidate(self, reason: str) -> None:
        if self.last_estimate is not None:
            self.last_estimate = replace(
                self.last_estimate,
                fresh=False,
                diagnostics={**(self.last_estimate.diagnostics or {}), "invalidated": reason},
            )
