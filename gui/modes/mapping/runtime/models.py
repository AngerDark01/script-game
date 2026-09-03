from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MappingTickResult:
    current_image: object
    combined_mask: object
    player_pos: tuple[int, int]
    capture_size: tuple[int, int]
