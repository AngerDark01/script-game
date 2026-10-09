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
    preview_frame: object | None = None


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

    def configure_live_follow(
        self,
        *,
        leader_role: str | None,
        target_roles: tuple[str, ...] | list[str] = (),
        initial_position: tuple[float, float] | None = None,
    ) -> None:
        configure = getattr(self.engine, "configure_live_target_policy", None)
        if callable(configure):
            configure(
                source_role=leader_role,
                target_roles=tuple(target_roles),
                initial_position=initial_position,
            )

    def poll(self) -> FollowUiState:
        self.engine.poll()
        return self.state()

    def state(self) -> FollowUiState:
        preview = getattr(self.engine, "preview_frame", None)
        return FollowUiState(
            self.engine.active,
            self.engine.snapshot(),
            self.engine.diagnostics(),
            preview() if callable(preview) else None,
        )

    def stop(self, *, reason: str = "user") -> FollowUiState:
        self.engine.stop(reason=reason)
        return self.state()


__all__ = ["FollowEngineUiAdapter", "FollowUiState"]
