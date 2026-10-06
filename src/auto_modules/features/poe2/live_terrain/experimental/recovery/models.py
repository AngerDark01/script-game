"""Pure recovery episode state; scheduling side effects stay in controllers."""

from __future__ import annotations

from dataclasses import dataclass, replace


@dataclass(frozen=True, slots=True)
class RecoveryEpisodeState:
    session_id: str | None = None
    active: bool = False
    reason: str | None = None
    schedule_count: int = 0
    retry_delay_ms: int = 0
    next_retry_delay_ms: int = 5_000

    def start(self, reason: str) -> "RecoveryEpisodeState":
        return replace(self, active=True, reason=reason)

    def schedule_retry(self, reason: str) -> "RecoveryEpisodeState":
        delay = self.next_retry_delay_ms if self.schedule_count else 5_000
        delay = max(5_000, min(15_000, int(delay)))
        return replace(
            self,
            active=True,
            reason=reason,
            schedule_count=self.schedule_count + 1,
            retry_delay_ms=delay,
            next_retry_delay_ms=min(15_000, delay * 2),
        )

    def clear(self) -> "RecoveryEpisodeState":
        return RecoveryEpisodeState(session_id=self.session_id)
