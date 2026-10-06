"""Protocols for effects used by experimental controllers.

These interfaces intentionally carry no Qt, Win32 or Host types.  The UI and
device integrations implement them; headless tests use the fakes in this
package.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


class CapturePort(Protocol):
    def capture(self, config: Any) -> Any: ...


class MemoryPort(Protocol):
    def read_player_positions(self) -> Any: ...


class WindowPort(Protocol):
    def is_game_foreground(self) -> bool: ...


class GamepadPort(Protocol):
    def acquire(self, controller: int) -> Any: ...


@dataclass(frozen=True, slots=True)
class AdapterBundle:
    capture: CapturePort | None = None
    memory: MemoryPort | None = None
    window: WindowPort | None = None
    gamepad: GamepadPort | None = None
