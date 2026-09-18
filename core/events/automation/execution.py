"""Pure source- and controller-scoped action-event execution."""

from __future__ import annotations

from dataclasses import dataclass
from threading import RLock
from typing import Callable, Iterable, Mapping

from core.events.gamepad_output import state_from_inputs
from core.runtime.event_session import EventSession

from .definitions import ExecutableEventDefinition


def _source(value: str) -> str:
    normalized = str(value or "").strip()
    if not normalized:
        raise ValueError("event source is required")
    return normalized if normalized.startswith("event:") else f"event:{normalized}"


def _controller_numbers(values: Iterable[int]) -> tuple[int, ...]:
    controllers = tuple(dict.fromkeys(int(value) for value in values))
    if not controllers or any(value not in (1, 2) for value in controllers):
        raise ValueError("controller must be either 1 or 2")
    return controllers


@dataclass(frozen=True)
class EventStateFrame:
    source: str
    controller: int
    state: dict


class EventExecutionRuntime:
    """Execute definitions without knowing their trigger or output device."""

    def __init__(
        self,
        definitions: Mapping[str, ExecutableEventDefinition],
        *,
        clock_ms: Callable[[], int],
    ) -> None:
        self._definitions = dict(definitions)
        self._clock_ms = clock_ms
        self._sessions: dict[tuple[str, int], EventSession] = {}
        self._lock = RLock()

    def replace_definitions(
        self,
        definitions: Mapping[str, ExecutableEventDefinition],
    ) -> None:
        with self._lock:
            self._definitions = dict(definitions)
            for session in self._sessions.values():
                session.definitions = self._definitions

    def start(
        self,
        source: str,
        event_name: str,
        controllers: Iterable[int],
        *,
        instance_id: str | None = None,
    ) -> bool:
        normalized_source = _source(source)
        controller_numbers = _controller_numbers(controllers)
        with self._lock:
            if event_name not in self._definitions:
                return False
            started = False
            for controller in controller_numbers:
                key = (normalized_source, controller)
                session = self._sessions.get(key)
                if session is None:
                    session = EventSession(self._definitions, clock_ms=self._clock_ms)
                    self._sessions[key] = session
                started = session.start(event_name, instance_id=instance_id) or started
            return started

    def cancel_source(self, source: str) -> tuple[EventStateFrame, ...]:
        normalized_source = _source(source)
        with self._lock:
            keys = sorted(key for key in self._sessions if key[0] == normalized_source)
            for key in keys:
                self._sessions.pop(key, None)
            return tuple(
                EventStateFrame(source=key[0], controller=key[1], state=state_from_inputs(()))
                for key in keys
            )

    def tick(self) -> tuple[EventStateFrame, ...]:
        with self._lock:
            return tuple(
                EventStateFrame(
                    source=source,
                    controller=controller,
                    state=state_from_inputs(session.tick()),
                )
                for (source, controller), session in sorted(self._sessions.items())
            )
