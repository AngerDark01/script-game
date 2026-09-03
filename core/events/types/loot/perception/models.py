from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class RegistrationSnapshot:
    valid: bool
    frame_origin_global: tuple[float, float] | None
    draw_scale: float
    frame_size: tuple[int, int] | None
    source: str = ""


@dataclass
class LootPerceptionRecord:
    confidence: float
    global_pos: tuple[float, float]
    source_local_pos: tuple[int, int]
    bbox_size: tuple[int, int]
    detected_at_ms: int
    metadata: dict[str, Any] = field(default_factory=dict)
    missing_streak: int = 0
