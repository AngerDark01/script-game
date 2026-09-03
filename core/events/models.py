from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from core.shared.frame_registration import FrameRegistration


class EventActionType(str, Enum):
    NONE = "none"
    MOVE_TO = "move_to"
    CLICK_SCREEN = "click_screen"
    PRESS_KEY = "press_key"
    WAIT = "wait"
    COMPLETE = "complete"
    FAIL = "fail"


class EventTaskState(str, Enum):
    OBSERVED = "observed"
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    IGNORED = "ignored"


@dataclass
class EventTick:
    now_ms: int
    raw_minimap_frame: Any = None
    player_global_pos: tuple[int, int] | None = None
    player_local_minimap_pos: tuple[int, int] | None = None
    localization_confidence: float = 0.0
    draw_scale: float = 1.0
    map_name: str = ""
    capture_provider: Any = None
    frame_registration: FrameRegistration | None = None
    event_tasks: list[Any] = field(default_factory=list)


@dataclass
class EventDetection:
    event_type: str
    confidence: float
    detected_at_ms: int
    local_minimap_pos: tuple[int, int]
    source: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class EventObservation:
    event_type: str
    confidence: float
    observed_at_ms: int
    global_pos: tuple[int, int]
    local_minimap_pos: tuple[int, int] | None = None
    source: str = ""
    sample_count: int = 1
    variance: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class EventTask:
    id: str
    event_type: str
    global_pos: tuple[int, int]
    first_seen_ms: int
    last_seen_ms: int
    state: EventTaskState = EventTaskState.OBSERVED
    priority: int = 0
    completed_at_ms: int | None = None
    failed_at_ms: int | None = None
    attempts: int = 0
    confidence: float = 0.0
    seen_count: int = 1
    metadata: dict[str, Any] = field(default_factory=dict)

    def mark_seen(self, observation: EventObservation, *, update_global_pos: bool = True) -> None:
        self.last_seen_ms = int(observation.observed_at_ms)
        self.confidence = max(float(self.confidence), float(observation.confidence))
        self.seen_count += 1
        if update_global_pos:
            self.global_pos = (int(observation.global_pos[0]), int(observation.global_pos[1]))
        self.metadata.update(observation.metadata)

    def mark_pending(self) -> None:
        if self.state == EventTaskState.OBSERVED:
            self.state = EventTaskState.PENDING

    def mark_running(self) -> None:
        self.state = EventTaskState.RUNNING
        self.attempts += 1

    def mark_completed(self, now_ms: int) -> None:
        self.state = EventTaskState.COMPLETED
        self.completed_at_ms = int(now_ms)

    def mark_failed(self, now_ms: int) -> None:
        self.state = EventTaskState.FAILED
        self.failed_at_ms = int(now_ms)

    def mark_ignored(self) -> None:
        self.state = EventTaskState.IGNORED


@dataclass
class EventAction:
    type: EventActionType
    target_global_pos: tuple[int, int] | None = None
    screen_pos: tuple[int, int] | None = None
    key: str | None = None
    wait_ms: int | None = None
    reason: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def none(cls, reason: str = "") -> "EventAction":
        return cls(type=EventActionType.NONE, reason=reason)

    @classmethod
    def move_to(
        cls,
        target_global_pos: tuple[int, int],
        reason: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> "EventAction":
        return cls(
            type=EventActionType.MOVE_TO,
            target_global_pos=(int(target_global_pos[0]), int(target_global_pos[1])),
            reason=reason,
            metadata=dict(metadata or {}),
        )

    @classmethod
    def click_screen(cls, screen_pos: tuple[int, int], reason: str = "") -> "EventAction":
        return cls(type=EventActionType.CLICK_SCREEN, screen_pos=(int(screen_pos[0]), int(screen_pos[1])), reason=reason)

    @classmethod
    def press_key(cls, key: str, reason: str = "") -> "EventAction":
        return cls(type=EventActionType.PRESS_KEY, key=str(key), reason=reason)

    @classmethod
    def wait(
        cls,
        wait_ms: int,
        reason: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> "EventAction":
        return cls(
            type=EventActionType.WAIT,
            wait_ms=int(wait_ms),
            reason=reason,
            metadata=dict(metadata or {}),
        )

    @classmethod
    def complete(cls, reason: str = "", metadata: dict[str, Any] | None = None) -> "EventAction":
        return cls(type=EventActionType.COMPLETE, reason=reason, metadata=dict(metadata or {}))

    @classmethod
    def fail(cls, reason: str = "") -> "EventAction":
        return cls(type=EventActionType.FAIL, reason=reason)
