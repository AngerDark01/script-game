"""Reusable, game-agnostic perception primitives."""

from .models import (
    BoundingBox,
    CoordinateSpace,
    DetectionEvidence,
    FrameContext,
    TargetDetection,
)

__all__ = [
    "BoundingBox",
    "CoordinateSpace",
    "DetectionEvidence",
    "FrameContext",
    "TargetDetection",
]
