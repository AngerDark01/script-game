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
from .builtins import create_default_algorithm_registry
from .pipeline import PerceptionPipeline, PerceptionRunResult
from .engine import PerceptionEngine

__all__ = [
    "BoundingBox",
    "CoordinateSpace",
    "DetectionEvidence",
    "FrameContext",
    "TargetDetection",
    "AlgorithmProfile",
    "TargetProfile",
    "AlgorithmRegistry",
    "create_default_algorithm_registry",
    "PerceptionPipeline",
    "PerceptionRunResult",
    "PerceptionEngine",
]
