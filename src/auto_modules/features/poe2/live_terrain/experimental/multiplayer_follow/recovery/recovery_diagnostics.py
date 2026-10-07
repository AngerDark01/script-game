"""Structured, low-cost diagnostics for recovery decisions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .recovery_state import RecoveryState


@dataclass(frozen=True)
class RecoveryDiagnostic:
    session_id: str
    generation: int
    role: str
    state: RecoveryState
    reason: str
    frame_available: bool
    frame_age_ms: float | None = None
    candidate_count: int = 0
    visual_attempt_ms: float = 0.0
    local_attempt_ms: float = 0.0
    memory_attempt_ms: float = 0.0
    global_attempt_ms: float = 0.0
    prediction_age_ms: float = 0.0
    prediction_uncertainty: float = 0.0
    next_state: RecoveryState | None = None
    result: str = "pending"
    details: tuple[tuple[str, Any], ...] = ()


__all__ = ["RecoveryDiagnostic"]
