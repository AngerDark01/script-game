"""Reusable, game-agnostic perception primitives."""

from .models import (
    BoundingBox,
    CoordinateSpace,
    DetectionEvidence,
    FrameContext,
    TargetDetection,
    PerceptionRunResult,
)
from .profiles import AlgorithmProfile, TargetProfile
from .registry import AlgorithmRegistry
from .builtins import create_default_algorithm_registry
from .pipeline import PerceptionPipeline
from .engine import PerceptionEngine

__all__ = [
    "BoundingBox",
    "CoordinateSpace",
    "DetectionEvidence",
    "FrameContext",
    "TargetDetection",
    "PerceptionRunResult",
    "AlgorithmProfile",
    "TargetProfile",
    "AlgorithmRegistry",
    "create_default_algorithm_registry",
    "PerceptionPipeline",
    "PerceptionEngine",
]
