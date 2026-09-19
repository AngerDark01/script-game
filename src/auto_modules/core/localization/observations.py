"""Generic frame-level entity observations for localization pipelines."""

from __future__ import annotations

from dataclasses import dataclass, field
from math import isfinite
from types import MappingProxyType
from typing import Any, Mapping


@dataclass(frozen=True)
class ObservationCandidate:
    """One entity candidate detected in a local frame coordinate space."""

    local_position: tuple[int, int]
    confidence: float
    identity_hint: str = ""
    evidence: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if len(self.local_position) != 2:
            raise ValueError("local_position must contain two values")
        if not all(isfinite(float(value)) for value in self.local_position):
            raise ValueError("local_position must be finite")
        if not 0.0 <= float(self.confidence) <= 1.0:
            raise ValueError("confidence must be between 0 and 1")
        object.__setattr__(self, "evidence", MappingProxyType(dict(self.evidence)))


@dataclass(frozen=True)
class ObservationFrame:
    """All entity candidates observed in one captured frame."""

    captured_at_ms: int
    candidates: tuple[ObservationCandidate, ...] = ()
    selected_index: int | None = None
    source: str = ""
    stale: bool = False

    def __post_init__(self) -> None:
        if int(self.captured_at_ms) < 0:
            raise ValueError("captured_at_ms must be non-negative")
        if self.selected_index is not None and not 0 <= self.selected_index < len(self.candidates):
            raise ValueError("selected_index must point to a candidate")

    @property
    def selected(self) -> ObservationCandidate | None:
        if self.selected_index is None:
            return None
        return self.candidates[self.selected_index]

    @property
    def is_fresh(self) -> bool:
        return not self.stale and self.selected is not None
