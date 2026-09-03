from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Point2D:
    x: float
    y: float

    def __post_init__(self) -> None:
        object.__setattr__(self, "x", float(self.x))
        object.__setattr__(self, "y", float(self.y))


@dataclass(frozen=True)
class CoordinateAnchor:
    """A matched point pair used to calibrate a coordinate transform."""

    source: Point2D
    target: Point2D
    label: str = ""


@dataclass(frozen=True)
class WindowRect:
    left: float
    top: float
    width: float
    height: float

    def __post_init__(self) -> None:
        if self.width <= 0 or self.height <= 0:
            raise ValueError("window dimensions must be positive")

    def from_normalized(self, point: Point2D) -> Point2D:
        return Point2D(
            self.left + point.x * self.width,
            self.top + point.y * self.height,
        )
