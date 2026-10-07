"""Low-cost timing aggregation for control ticks."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ControlTiming:
    input_ms: float = 0.0
    prediction_ms: float = 0.0
    fusion_ms: float = 0.0
    route_ms: float = 0.0
    recovery_ms: float = 0.0
    output_ms: float = 0.0
    total_ms: float = 0.0

    def as_dict(self) -> dict[str, float]:
        return {name: float(getattr(self, name)) for name in self.__dataclass_fields__}
