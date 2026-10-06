"""Qt-free state contracts shared by the PoE2 experiment controllers."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from enum import StrEnum
from typing import Any, Mapping


class ExperimentPhase(StrEnum):
    IDLE = "idle"
    STARTING = "starting"
    RUNNING = "running"
    WAITING_FOREGROUND = "waiting_foreground"
    TRACKING = "tracking"
    RECOVERING = "recovering"
    DEGRADED = "degraded"
    STOPPING = "stopping"
    STOPPED = "stopped"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class ExperimentSessionState:
    session_id: str | None = None
    phase: ExperimentPhase = ExperimentPhase.IDLE
    started_at_ms: int | None = None
    map_instance_id: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def transition(self, phase: ExperimentPhase, **changes: Any) -> "ExperimentSessionState":
        return replace(self, phase=phase, **changes)
