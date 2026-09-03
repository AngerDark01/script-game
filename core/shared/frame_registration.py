from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class FrameRegistration:
    """Wall-registration metadata for one minimap frame."""

    valid: bool
    confidence: float = 0.0
    frame_origin_global: tuple[float, float] | None = None
    draw_scale: float = 1.0
    player_global_pos: tuple[float, float] | None = None
    player_local_minimap_pos: tuple[int, int] | None = None
    source: str = ""
    frame_size: tuple[int, int] | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
