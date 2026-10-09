"""Page-facing adapter for the modular follow engine.

This module deliberately contains no route, tracking, recovery or process
logic.  A Qt page can own its timer and call ``poll``; the engine remains the
only owner of worker and output lifecycles.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence

from auto_modules.features.poe2.live_terrain.experimental.follow_engine.engine import FollowEngineStart
from auto_modules.features.poe2.live_terrain.experimental.follow_engine.ui_adapter import (
    FollowEngineUiAdapter,
    FollowUiState,
)


class Poe2FollowEnginePageAdapter:
    """Translate page events into engine operations and state callbacks."""

    def __init__(
        self,
        engine: FollowEngineUiAdapter,
        *,
        on_state: Callable[[FollowUiState], None] | None = None,
        initial_positions: Mapping[str, tuple[float, float]] | None = None,
        leader_role: str | None = None,
        target_roles: Sequence[str] = (),
    ) -> None:
        self.engine = engine
        self.on_state = on_state
        self._initial_positions = {
            str(role): (float(point[0]), float(point[1]))
            for role, point in (initial_positions or {}).items()
        }
        self._leader_role = None if leader_role is None else str(leader_role)
        self._target_roles = tuple(str(role) for role in target_roles)
        self._last_sent_live_target: tuple[float, float] | None = None
        self._engine_live_policy_bound = False

    def configure_live_follow(
        self,
        *,
        leader_role: str | None,
        target_roles: Sequence[str],
    ) -> None:
        """Set the page-level continuous target policy without changing the engine."""
        self._leader_role = None if leader_role is None else str(leader_role)
        self._target_roles = tuple(str(role) for role in target_roles)
        self._last_sent_live_target = None
        configure = getattr(self.engine, "configure_live_follow", None)
        if callable(configure):
            self._engine_live_policy_bound = True
            configure(
                leader_role=self._leader_role,
                target_roles=self._target_roles,
                initial_position=(
                    self._initial_positions.get(self._leader_role)
                    if self._leader_role is not None else None
                ),
            )

    def start(self, config: FollowEngineStart) -> FollowUiState:
        state = self.engine.start(config)
        self._refresh_live_targets(state)
        return self._publish(state)

    def target_clicked(self, role_id: str, target: tuple[float, float] | None) -> FollowUiState:
        return self._publish(self.engine.update_target(role_id, target))

    def poll(self) -> FollowUiState:
        state = self.engine.poll()
        self._refresh_live_targets(state)
        return self._publish(state)

    def stop(self, *, reason: str = "user") -> FollowUiState:
        return self._publish(self.engine.stop(reason=reason))

    def _publish(self, state: FollowUiState) -> FollowUiState:
        if self.on_state is not None:
            self.on_state(state)
        return state

    def _refresh_live_targets(self, state: FollowUiState) -> None:
        # When the engine owns the live observation stream, a page-side
        # snapshot relay would write an older fused position after the fresh
        # observation in the same UI poll.  Keep this fallback only for legacy
        # adapters that do not expose the engine policy contract.
        if self._engine_live_policy_bound:
            return
        if self._leader_role is None or not self._target_roles:
            return
        leader = None
        if state.snapshot is not None:
            leader_state = state.snapshot.roles.get(self._leader_role)
            if leader_state is not None:
                leader = leader_state.position_native
        if leader is None:
            leader = self._initial_positions.get(self._leader_role)
        if leader is None or not state.active:
            return
        if self._last_sent_live_target is not None:
            dx = float(leader[0]) - self._last_sent_live_target[0]
            dy = float(leader[1]) - self._last_sent_live_target[1]
            if (dx * dx + dy * dy) < 0.05 * 0.05:
                return
        for role_id in self._target_roles:
            if role_id == self._leader_role:
                continue
            try:
                self.engine.update_target(role_id, leader)
            except RuntimeError:
                # The engine may have been stopped by the explicit stop button
                # between poll and target refresh; the page owns that race.
                return
        self._last_sent_live_target = (float(leader[0]), float(leader[1]))


__all__ = ["Poe2FollowEnginePageAdapter"]
