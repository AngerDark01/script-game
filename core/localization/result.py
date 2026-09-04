from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from core.perception.models import CoordinateSpace


@dataclass(frozen=True)
class LocalizationResult:
    """Typed outcome of one legacy minimap-to-global-map localization attempt."""

    position: tuple[float, float] | None
    confidence: float
    coordinate_space: CoordinateSpace = CoordinateSpace.GLOBAL_MAP
    source: str = ""
    registration_valid: bool | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    @property
    def localized_pos(self) -> tuple[float, float] | None:
        return self.position

    @property
    def is_localized(self) -> bool:
        return self.position is not None

    def as_legacy_tuple(self) -> tuple[float | None, float | None, float]:
        """Return the historical ``(global_x, global_y, confidence)`` shape."""
        if self.position is None:
            return None, None, self.confidence
        return self.position[0], self.position[1], self.confidence

    @classmethod
    def from_legacy_tuple(cls, value, *, registration=None) -> "LocalizationResult":
        """Adapt one legacy localization return value and snapshot its registration."""
        global_x, global_y, confidence = value
        position = None
        if global_x is not None and global_y is not None:
            position = float(global_x), float(global_y)
        return cls(
            position=position,
            confidence=float(confidence or 0.0),
            source=str(getattr(registration, "source", "") or ""),
            registration_valid=(
                bool(registration.valid)
                if registration is not None and getattr(registration, "valid", None) is not None
                else None
            ),
            metadata=dict(getattr(registration, "metadata", {}) or {}),
        )
