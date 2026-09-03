from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping


class CoordinateSpace(str, Enum):
    """Coordinate systems that a detector or mapper may produce."""

    FULL_SCREEN = "full_screen"
    GAME_WINDOW = "game_window"
    VIEWPORT = "viewport"
    MINIMAP = "minimap"
    GLOBAL_MAP = "global_map"
    NORMALIZED = "normalized"


@dataclass(frozen=True)
class BoundingBox:
    """A rectangle expressed in the detection result's coordinate space."""

    left: float
    top: float
    width: float
    height: float

    @property
    def center(self) -> tuple[float, float]:
        return (self.left + self.width / 2.0, self.top + self.height / 2.0)

    def normalized(self, frame_width: float, frame_height: float) -> tuple[float, float, float, float]:
        if frame_width <= 0 or frame_height <= 0:
            raise ValueError("frame dimensions must be positive")
        return (
            self.left / frame_width,
            self.top / frame_height,
            self.width / frame_width,
            self.height / frame_height,
        )


@dataclass(frozen=True)
class FrameContext:
    """An image plus capture metadata supplied to one detector run."""

    image: Any
    captured_at_ms: int | None = None
    source: str = ""
    width: int | None = None
    height: int | None = None
    coordinate_space: CoordinateSpace = CoordinateSpace.FULL_SCREEN
    metadata: Mapping[str, Any] = field(default_factory=dict)

    @property
    def size(self) -> tuple[int | None, int | None]:
        return self.width, self.height


@dataclass(frozen=True)
class DetectionEvidence:
    """One algorithm's evidence for a target candidate."""

    algorithm_id: str
    score: float
    details: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class TargetDetection:
    """Normalized output shared by all target recognition algorithms."""

    target_type: str
    center: tuple[float, float]
    coordinate_space: CoordinateSpace
    confidence: float
    bbox: BoundingBox | None = None
    target_name: str | None = None
    state: str = "candidate"
    source: str = ""
    detected_at_ms: int | None = None
    text: str | None = None
    evidence: tuple[DetectionEvidence, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.target_type:
            raise ValueError("target_type must not be empty")
        if len(self.center) != 2:
            raise ValueError("center must contain exactly two coordinates")
        if not 0.0 <= float(self.confidence) <= 1.0:
            raise ValueError("confidence must be between 0 and 1")


@dataclass(frozen=True)
class PerceptionRunResult:
    """Pipeline result with additive confirmation and selection state."""

    detections: tuple[TargetDetection, ...]
    by_algorithm: Mapping[str, tuple[TargetDetection, ...]] = field(default_factory=dict)
    errors: Mapping[str, str] = field(default_factory=dict)
    selected: TargetDetection | None = None
    confirmed: bool = True
    confirmation_counts: tuple[int, ...] = ()
