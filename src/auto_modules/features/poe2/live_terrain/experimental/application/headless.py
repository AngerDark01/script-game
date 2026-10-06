"""Small headless runner used by replay and contract tests."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .models import ExperimentPhase
from .runtime import ExperimentRuntime
from ..diagnostics import DiagnosticEvent, EventRecorder


@dataclass(frozen=True, slots=True)
class HeadlessTick:
    tick_id: int
    captured_at_ms: int
    payload: Any


class HeadlessExperiment:
    """Runs lifecycle and diagnostics without QApplication or real devices."""

    def __init__(self, *, session_id: str = "replay", diagnostics: EventRecorder | None = None) -> None:
        self.runtime = ExperimentRuntime()
        self.diagnostics = diagnostics or EventRecorder()
        self.session_id = session_id
        self.tick_id = 0

    def start(self, started_at_ms: int = 0) -> None:
        self.runtime.start(self.session_id, started_at_ms=started_at_ms)
        self.diagnostics.record(DiagnosticEvent(self.session_id, "started"))

    def ingest(self, captured_at_ms: int, payload: Any) -> HeadlessTick:
        if self.runtime.state.phase not in {ExperimentPhase.RUNNING, ExperimentPhase.RECOVERING}:
            raise RuntimeError("headless experiment is not running")
        self.tick_id += 1
        tick = HeadlessTick(self.tick_id, int(captured_at_ms), payload)
        self.diagnostics.record(DiagnosticEvent(
            self.session_id, "frame_ingested", tick_id=tick.tick_id,
            frame_id=tick.captured_at_ms, payload={"has_payload": payload is not None},
        ))
        return tick

    def recover(self, reason: str) -> None:
        self.runtime.transition(ExperimentPhase.RECOVERING)
        self.diagnostics.record(DiagnosticEvent(self.session_id, "recovering", reason=reason))

    def stop(self) -> None:
        self.runtime.stop()
        self.diagnostics.record(DiagnosticEvent(self.session_id, "stopped"))
