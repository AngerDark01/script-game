"""Bounded, serializable experiment diagnostics."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from time import perf_counter
from typing import Any


@dataclass(frozen=True, slots=True)
class DiagnosticEvent:
    session_id: str | None
    kind: str
    tick_id: int | None = None
    frame_id: int | None = None
    elapsed_ms: float | None = None
    reason: str | None = None
    payload: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


class EventRecorder:
    def __init__(self, *, max_events: int = 2_000) -> None:
        self.max_events = max(1, int(max_events))
        self.events: list[DiagnosticEvent] = []

    def record(self, event: DiagnosticEvent) -> DiagnosticEvent:
        self.events.append(event)
        del self.events[:-self.max_events]
        return event

    def measure(self, session_id: str | None, kind: str, *, tick_id: int | None = None):
        started = perf_counter()

        def finish(**payload: Any) -> DiagnosticEvent:
            return self.record(
                DiagnosticEvent(
                    session_id,
                    kind,
                    tick_id=tick_id,
                    elapsed_ms=(perf_counter() - started) * 1000.0,
                    payload=payload,
                )
            )

        return finish
