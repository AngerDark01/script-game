"""Pickle-safe evidence of submitted input, never proof of game displacement."""
from dataclasses import dataclass
import math


@dataclass(frozen=True, slots=True)
class ExecutionReceipt:
    generation: int
    sequence: int
    role_id: str
    vector: tuple[float, float]
    accepted_at_ms: int
    valid_for_ms: int
    control_tick: int = 0
    target_revision: int = 0
    visual_sequence: int = -1

    def __post_init__(self):
        if self.generation < 1 or self.sequence < 1 or not self.role_id or self.accepted_at_ms < 0 or self.valid_for_ms < 0:
            raise ValueError("invalid execution receipt header")
        if len(self.vector) != 2 or any(not math.isfinite(v) or abs(v) > 1.01 for v in self.vector):
            raise ValueError("invalid execution vector")
