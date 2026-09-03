from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class NavigationTaskKind(str, Enum):
    REQUIRED = "required"
    EXIT = "exit"
    EVENT = "event"


class NavigationTaskState(str, Enum):
    PENDING = "pending"
    MOVING = "moving"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"
    IGNORED = "ignored"


class NavigationIntentType(str, Enum):
    NONE = "none"
    MOVE_MAP = "move_map"
    CLICK_SCREEN = "click_screen"
    PRESS_KEY = "press_key"
    WAIT = "wait"
    ARRIVED = "arrived"
    FAILED = "failed"


@dataclass
class RouteProjection:
    point: tuple[float, float]
    progress: float
    segment_index: int
    deviation: float


@dataclass
class RouteAnchor:
    index: int
    point: tuple[float, float]
    progress: float


@dataclass
class NavigationTask:
    id: str
    kind: NavigationTaskKind
    target_pos: tuple[float, float]
    state: NavigationTaskState = NavigationTaskState.PENDING
    priority: int = 0
    route_progress: float | None = None
    source_ref: Any = None
    required_index: int | None = None
    event_type: str | None = None
    radius: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class MovementStep:
    path: list[tuple[float, float]] = field(default_factory=list)
    subgoal: tuple[float, float] | None = None
    path_kind: str = "none"
    should_click: bool = False
    force_click_target: bool = False
    deviation: float = 0.0
    reason: str = ""
    task_id: str | None = None
    target_pos: tuple[float, float] | None = None


@dataclass
class NavigationIntent:
    type: NavigationIntentType = NavigationIntentType.NONE
    task_id: str | None = None
    task_kind: str | None = None
    player_pos: tuple[float, float] | None = None
    target_pos: tuple[float, float] | None = None
    subgoal: tuple[float, float] | None = None
    path: list[tuple[float, float]] = field(default_factory=list)
    path_kind: str = "none"
    required_index: int | None = None
    message: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
