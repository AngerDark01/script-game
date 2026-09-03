"""Composable decision stages owned by the perception engine."""

from .confirmation import ConfirmationResult, ConfirmationTracker
from .fusion import fuse_candidates
from .runner import DetectorRunResult, DetectorRunner
from .selection import select_candidate

__all__ = [
    "ConfirmationResult",
    "ConfirmationTracker",
    "DetectorRunResult",
    "DetectorRunner",
    "fuse_candidates",
    "select_candidate",
]
