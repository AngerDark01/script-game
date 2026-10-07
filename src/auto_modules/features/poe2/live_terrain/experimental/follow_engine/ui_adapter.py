"""Small adapter for pages that need to display follow-engine state."""

from __future__ import annotations

from dataclasses import dataclass
from .contracts import FusionSnapshot
from .engine import FollowEnginePort, FollowEngineStart


@dataclass(frozen=True, slots=True)
class FollowUiState:
    active: bool
    snapshot: FusionSnapshot | None
    diagnostics: dict[str, object]


class FollowEngineUiAdapter:
    """Keep UI concerns to target events, polling and read-only state."""

    def __init__(self, engine: FollowEnginePort) -> None:
        self.engine = engine

    def start(self, config: FollowEngineStart) -> FollowUiState:
        self.engine.start(config)
        return self.state()

    def update_target(self, role_id: str, target: tuple[float, float] | None) -> FollowUiState:
        self.engine.update_target(target, role_id=role_id)
        return self.state()

    def poll(self) -> FollowUiState:
        self.engine.poll()
        return self.state()

    def state(self) -> FollowUiState:
        return FollowUiState(self.engine.active, self.engine.snapshot(), self.engine.diagnostics())

    def stop(self, *, reason: str = "user") -> FollowUiState:
        self.engine.stop(reason=reason)
        return self.state()


__all__ = ["FollowEngineUiAdapter", "FollowUiState"]
