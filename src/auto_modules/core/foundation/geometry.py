"""Dependency-free 2D geometry primitives."""

from __future__ import annotations

from dataclasses import dataclass
from math import hypot


@dataclass(frozen=True)
class Vector2:
    x: float
    y: float

    def __add__(self, other: Vector2) -> Vector2:
        return Vector2(self.x + other.x, self.y + other.y)

    def __sub__(self, other: Vector2) -> Vector2:
        return Vector2(self.x - other.x, self.y - other.y)

    def __mul__(self, scalar: float) -> Vector2:
        return Vector2(self.x * scalar, self.y * scalar)

    def length(self) -> float:
        return hypot(self.x, self.y)


@dataclass(frozen=True)
class Point2:
    x: float
    y: float

    def __add__(self, vector: Vector2) -> Point2:
        return Point2(self.x + vector.x, self.y + vector.y)

    def __sub__(self, other: Point2) -> Vector2:
        return Vector2(self.x - other.x, self.y - other.y)

    def distance_to(self, other: Point2) -> float:
        return (self - other).length()


@dataclass(frozen=True)
class Transform2D:
    scale: float = 1.0
    offset: Vector2 = Vector2(0.0, 0.0)

    def apply(self, point: Point2) -> Point2:
        return Point2(point.x * self.scale + self.offset.x, point.y * self.scale + self.offset.y)
