"""Keyboard action adapter with a narrow injectable platform protocol."""

from __future__ import annotations

import time
from typing import Callable, Protocol

from .contracts import ActionCommand, ActionKind, ActionResult, KeyboardTarget


class KeyboardDevice(Protocol):
    """The minimal keyboard capability used by the generic adapter."""

    def key_down(self, key: str) -> None: ...

    def key_up(self, key: str) -> None: ...


class KeyboardActionAdapter:
    """Deliver key down, key up, and chord commands without workflow knowledge."""

    def __init__(
        self,
        *,
        device: KeyboardDevice,
        clock_ms: Callable[[], int] | None = None,
        device_id: str = "keyboard",
    ) -> None:
        if not device_id.strip():
            raise ValueError("device_id must not be empty")
        self._device = device
        self._clock_ms = clock_ms or (lambda: int(time.monotonic() * 1000))
        self._device_id = device_id

    def execute(self, command: ActionCommand) -> ActionResult:
        if not isinstance(command, ActionCommand):
            raise TypeError("command must be an ActionCommand")
        if not isinstance(command.target, KeyboardTarget) or command.kind not in {
            ActionKind.KEY_DOWN,
            ActionKind.KEY_UP,
            ActionKind.KEY_CHORD,
        }:
            raise ValueError("keyboard adapter requires a keyboard action command")

        started_at_ms = int(self._clock_ms())
        if command.kind is ActionKind.KEY_DOWN:
            self._device.key_down(command.target.keys[0])
        elif command.kind is ActionKind.KEY_UP:
            self._device.key_up(command.target.keys[0])
        else:
            self._execute_chord(command.target.keys)
        completed_at_ms = int(self._clock_ms())
        return ActionResult(
            executed=True,
            device_id=self._device_id,
            kind=command.kind,
            started_at_ms=started_at_ms,
            completed_at_ms=completed_at_ms,
            target=command.target,
            metadata={"keys": command.target.keys},
        )

    def _execute_chord(self, keys: tuple[str, ...]) -> None:
        pressed: list[str] = []
        try:
            for key in keys:
                self._device.key_down(key)
                pressed.append(key)
        finally:
            for key in reversed(pressed):
                self._device.key_up(key)
