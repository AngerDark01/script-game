from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class AnchorPathResult:
    path: list[tuple[int, int]]
    path_kind: str
    used_anchor_count: int = 0
    anchor_points: list[tuple[int, int]] = field(default_factory=list)
