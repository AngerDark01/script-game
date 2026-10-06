"""Pure movement decisions exchanged between controller and adapters."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class MotionDecision:
    vector: tuple[float, float]
    duration_ms: int
    reason: str
    release_output: bool = False
    target: tuple[float, float] | None = None
