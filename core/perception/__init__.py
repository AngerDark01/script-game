"""Reusable, game-agnostic perception primitives."""

from .models import (
    BoundingBox,
    CoordinateSpace,
    DetectionEvidence,
    FrameContext,
    TargetDetection,
)
from .profiles import AlgorithmProfile, TargetProfile
from .registry import AlgorithmRegistry

__all__ = [
    "BoundingBox",
    "CoordinateSpace",
    "DetectionEvidence",
    "FrameContext",
    "TargetDetection",
    "AlgorithmProfile",
    "TargetProfile",
    "AlgorithmRegistry",
]
