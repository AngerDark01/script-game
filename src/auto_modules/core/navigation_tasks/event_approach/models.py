from __future__ import annotations

from dataclasses import dataclass

from ..models import NavigationIntent


@dataclass
class EventApproachConfig:
    enabled: bool = True
    game_view_map_size: int = 520
    visible_margin: int = 30
    approach_lookahead: float = 36.0
    click_cooldown_ms: int = 800
    stop_radius: float = 18.0
    settle_ms: int = 800
    stable_frames: int = 2
    max_motion_per_frame: float = 8.0


@dataclass
class EventApproachResult:
    ready: bool = False
    intent: NavigationIntent | None = None
    phase: str = "far"
    approach_target: tuple[float, float] | None = None
    reason: str = ""
    visible: bool = False
    became_visible: bool = False
