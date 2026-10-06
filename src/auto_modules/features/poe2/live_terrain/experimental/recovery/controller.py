"""Policy-only recovery controller used by the experiment façade.

The controller owns episode/backoff decisions.  Starting a worker, releasing a
gamepad, and updating Qt are deliberately supplied as callbacks by the caller.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from .models import RecoveryEpisodeState


@dataclass(frozen=True, slots=True)
class RecoveryObservation:
    reason: str
    recovery_requested: bool = False
    contact_evidence: Mapping[str, object] | None = None
    stale_duration_ms: int | None = None
    foreground: bool = True


@dataclass(frozen=True, slots=True)
class RecoveryDecision:
    requested: bool
    reason: str
    release_output: bool = False
    retry_after_ms: int | None = None
    suppressed: bool = False


class RecoveryController:
    """Keep one recovery episode and bound retry pressure."""

    def __init__(self, *, session_id: str | None = None) -> None:
        self._state = RecoveryEpisodeState(session_id=session_id)

    @property
    def state(self) -> RecoveryEpisodeState:
        return self._state

    def observe(self, observation: RecoveryObservation) -> RecoveryDecision:
        evidence = observation.contact_evidence or {}
        explicit = bool(observation.recovery_requested or evidence.get("recovery_required"))
        if not explicit:
            return RecoveryDecision(False, observation.reason)
        if self._state.active:
            self._state = RecoveryEpisodeState(
                session_id=self._state.session_id,
                active=True,
                reason=self._state.reason,
                schedule_count=self._state.schedule_count,
                retry_delay_ms=self._state.retry_delay_ms,
                next_retry_delay_ms=self._state.next_retry_delay_ms,
            )
            return RecoveryDecision(False, observation.reason, suppressed=True)
        self._state = self._state.start(observation.reason)
        return RecoveryDecision(True, observation.reason, release_output=True)

    def schedule_retry(self, reason: str) -> RecoveryDecision:
        self._state = self._state.schedule_retry(reason)
        return RecoveryDecision(
            requested=True,
            reason=reason,
            release_output=True,
            retry_after_ms=self._state.retry_delay_ms,
        )

    def clear(self, reason: str = "fresh_observation") -> None:
        self._state = self._state.clear()
