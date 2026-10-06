"""Small lifecycle runtime shared by PoE2 experimental controllers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .models import ExperimentPhase, ExperimentSessionState


@dataclass(frozen=True, slots=True)
class RuntimeEvent:
    session_id: str
    kind: str
    payload: Any = None


class ExperimentRuntime:
    def __init__(self) -> None:
        self.state = ExperimentSessionState()

    def start(self, session_id: str, *, started_at_ms: int | None = None) -> RuntimeEvent:
        self.state = ExperimentSessionState(
            session_id=session_id,
            phase=ExperimentPhase.RUNNING,
            started_at_ms=started_at_ms,
        )
        return RuntimeEvent(session_id, "started")

    def transition(self, phase: ExperimentPhase, **changes: Any) -> RuntimeEvent | None:
        if self.state.session_id is None:
            return None
        self.state = self.state.transition(phase, **changes)
        return RuntimeEvent(self.state.session_id, "state_changed", self.state)

    def stop(self, *, failed: bool = False) -> RuntimeEvent | None:
        if self.state.session_id is None:
            return None
        phase = ExperimentPhase.FAILED if failed else ExperimentPhase.STOPPED
        self.state = self.state.transition(phase)
        return RuntimeEvent(self.state.session_id, "stopped", self.state)

    def accepts(self, session_id: str | None) -> bool:
        return bool(session_id and session_id == self.state.session_id)
