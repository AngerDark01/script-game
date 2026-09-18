from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class PositionSample:
    global_pos: tuple[float, float]
    local_pos: tuple[int, int]
    confidence: float
    seen_ms: int
    source: str
    metadata: dict


@dataclass
class PositionCluster:
    event_type: str
    samples: list[PositionSample] = field(default_factory=list)
    last_emitted_ms: int = 0
    last_seen_ms: int = 0

    def center(self) -> tuple[float, float]:
        total_weight = sum(max(0.01, sample.confidence) for sample in self.samples)
        if total_weight <= 0:
            return self.samples[-1].global_pos
        x = sum(sample.global_pos[0] * max(0.01, sample.confidence) for sample in self.samples) / total_weight
        y = sum(sample.global_pos[1] * max(0.01, sample.confidence) for sample in self.samples) / total_weight
        return x, y

    def variance(self) -> float:
        if len(self.samples) <= 1:
            return 0.0
        cx, cy = self.center()
        return float(
            sum((sample.global_pos[0] - cx) ** 2 + (sample.global_pos[1] - cy) ** 2 for sample in self.samples)
            / len(self.samples)
        )

    def confidence(self) -> float:
        if not self.samples:
            return 0.0
        return float(max(sample.confidence for sample in self.samples))
