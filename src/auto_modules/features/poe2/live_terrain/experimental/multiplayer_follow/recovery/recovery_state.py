"""Explicit recovery states and escalation levels."""

from __future__ import annotations

from enum import Enum, IntEnum


class RecoveryState(str, Enum):
    TRACKING = "tracking"
    VISUAL_DEGRADED = "visual_degraded"
    LOCAL_REANCHOR_PENDING = "local_reanchor_pending"
    LOCAL_REANCHORING = "local_reanchoring"
    PREDICTING = "predicting"
    MEMORY_REANCHOR_PENDING = "memory_reanchor_pending"
    MEMORY_REANCHORING = "memory_reanchoring"
    GLOBAL_REANCHOR_PENDING = "global_reanchor_pending"
    GLOBAL_REANCHORING = "global_reanchoring"
    FOLLOW_HOLD = "follow_hold"
    FOLLOW_REARMING = "follow_rearming"


class RecoveryLevel(IntEnum):
    VISUAL = 0
    LOCAL = 1
    MEMORY = 2
    GLOBAL = 3


__all__ = ["RecoveryLevel", "RecoveryState"]
