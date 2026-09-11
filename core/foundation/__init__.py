"""Small dependency-free primitives shared by runtime modules."""

from .clock import MonotonicClock
from .geometry import Point2, Transform2D, Vector2

__all__ = ["MonotonicClock", "Point2", "Transform2D", "Vector2"]
