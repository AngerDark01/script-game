"""Page-facing adapter for the modular follow engine.

This module deliberately contains no route, tracking, recovery or process
logic.  A Qt page can own its timer and call ``poll``; the engine remains the
only owner of worker and output lifecycles.
"""

from __future__ import annotations

from collections.abc import Callable

from auto_modules.features.poe2.live_terrain.experimental.follow_engine.engine import FollowEngineStart
from auto_modules.features.poe2.live_terrain.experimental.follow_engine.ui_adapter import (
    FollowEngineUiAdapter,
    FollowUiState,
)


class Poe2FollowEnginePageAdapter:
    """Translate page events into engine operations and state callbacks."""

    def __init__(self, engine: FollowEngineUiAdapter, *, on_state: Callable[[FollowUiState], None] | None = None) -> None:
        self.engine = engine
        self.on_state = on_state

    def start(self, config: FollowEngineStart) -> FollowUiState:
        return self._publish(self.engine.start(config))

    def target_clicked(self, role_id: str, target: tuple[float, float] | None) -> FollowUiState:
        return self._publish(self.engine.update_target(role_id, target))

    def poll(self) -> FollowUiState:
        return self._publish(self.engine.poll())

    def stop(self, *, reason: str = "user") -> FollowUiState:
        return self._publish(self.engine.stop(reason=reason))

    def _publish(self, state: FollowUiState) -> FollowUiState:
        if self.on_state is not None:
            self.on_state(state)
        return state


__all__ = ["Poe2FollowEnginePageAdapter"]
