from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class LocalizationSnapshot:
    pos: Any
    confidence: float
    frame_registration: Any = None


@dataclass
class PlanningSnapshot:
    wall_map: Any
    pathfinder: Any
    explored_map: Any = None
    lookahead_distance: float = 0.0


@dataclass
class EventRuntimeSnapshot:
    coordinator: Any = None
    tick: Any = None
    manual_event_only: bool = False


@dataclass
class NavigationUpdateContext:
    now_ms: int
    localization: LocalizationSnapshot
    route: dict | None
    planning: PlanningSnapshot
    events: EventRuntimeSnapshot
