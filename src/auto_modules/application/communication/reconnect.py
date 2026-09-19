"""Generation fencing and bounded retry policy for peer reconnects."""

from __future__ import annotations

from dataclasses import dataclass, field

from auto_modules.core.communication.contracts import PeerId


@dataclass(slots=True)
class ReconnectController:
    """Keep reconnect attempts deterministic and fence stale work."""

    retry_delays: tuple[float, ...] = (1.0, 2.0, 5.0, 15.0, 30.0)
    _generations: dict[PeerId, int] = field(default_factory=dict)
    _attempts: dict[PeerId, int] = field(default_factory=dict)
    _blocked: set[PeerId] = field(default_factory=set)

    def new_session(self, peer_id: PeerId) -> int:
        generation = self._generations.get(peer_id, 0) + 1
        self._generations[peer_id] = generation
        self._attempts[peer_id] = 0
        self._blocked.discard(peer_id)
        return generation

    def generation(self, peer_id: PeerId) -> int:
        return self._generations.get(peer_id, 0)

    def fence(self, peer_id: PeerId, *, block_recovery: bool) -> int:
        generation = self._generations.get(peer_id, 0) + 1
        self._generations[peer_id] = generation
        self._attempts[peer_id] = 0
        if block_recovery:
            self._blocked.add(peer_id)
        return generation

    def can_recover(self, peer_id: PeerId) -> bool:
        return peer_id not in self._blocked

    def next_delay(self, peer_id: PeerId) -> float:
        attempt = self._attempts.get(peer_id, 0)
        self._attempts[peer_id] = attempt + 1
        return self.retry_delays[min(attempt, len(self.retry_delays) - 1)]

