"""Side-effect ports used by experiment controllers."""

from __future__ import annotations

from typing import Any, Protocol


class CapturePort(Protocol):
    def capture(self, config: Any) -> Any: ...


class MemoryPort(Protocol):
    def read_player_positions(self) -> Any: ...


class WindowPort(Protocol):
    def is_game_foreground(self) -> bool: ...


class GamepadPort(Protocol):
    def acquire(self, controller: int) -> Any: ...


class TargetSource(Protocol):
    def latest(self) -> tuple[float, float] | None: ...
