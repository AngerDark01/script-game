"""Physical peer-session state kept by the communication manager."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from auto_modules.core.communication.contracts import Capability, PeerId


@dataclass(slots=True)
class PeerSession:
    peer_id: PeerId
    connection: Any
    generation: int
    leases: dict[str, Capability] = field(default_factory=dict)
    active: bool = True

    def add_lease(self, token: str, capability: Capability) -> None:
        self.leases[token] = capability

    def remove_lease(self, token: str) -> None:
        self.leases.pop(token, None)

    @property
    def capabilities(self) -> set[Capability]:
        return set(self.leases.values())

