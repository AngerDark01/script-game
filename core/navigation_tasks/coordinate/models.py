from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class CoordinateRelocalizationRequest:
    reason: str
    requested_at_ms: int
    score: int = 0
    signals: tuple[str, ...] = field(default_factory=tuple)
    details: dict[str, Any] = field(default_factory=dict)
