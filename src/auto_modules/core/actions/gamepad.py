"""Adapter from generic action commands to the independent Virtual Gamepad host."""

from __future__ import annotations

import time
from typing import Callable, Protocol

from .contracts import (
    ActionCommand,
    ActionKind,
    ActionResult,
    GamepadButtonTarget,
    GamepadResetTarget,
    GamepadStickTarget,
    GamepadTriggerTarget,
)


class VirtualGamepadDevice(Protocol):
    """Subset of the independent VirtualGamepadClient needed for primitive actions."""

    def button(self, button: str, action: str, source: str, ttl_ms: int | None, controller: int) -> None: ...

    def set_axis(self, axis: str, value: int, source: str, ttl_ms: int | None, controller: int) -> None: ...

    def set_trigger(self, trigger: str, value: int, source: str, ttl_ms: int | None, controller: int) -> None: ...

    def reset(self, controller: int) -> None: ...


class VirtualGamepadActionAdapter:
    """Deliver primitive Xbox actions through the existing independent host client."""

    def __init__(
        self,
        *,
        device: VirtualGamepadDevice,
        clock_ms: Callable[[], int] | None = None,
        device_id: str = "virtual_gamepad",
    ) -> None:
        if not device_id.strip():
            raise ValueError("device_id must not be empty")
        self._device = device
        self._clock_ms = clock_ms or (lambda: int(time.monotonic() * 1000))
        self._device_id = device_id

    def close(self) -> None:
        """Close the borrowed named-pipe client when this adapter owns its connection."""
        close = getattr(self._device, "close", None)
        if callable(close):
            close()

    def execute(self, command: ActionCommand) -> ActionResult:
        if not isinstance(command, ActionCommand):
            raise TypeError("command must be an ActionCommand")
        started_at_ms = int(self._clock_ms())
        target = command.target

        if command.kind is ActionKind.GAMEPAD_BUTTON and isinstance(target, GamepadButtonTarget):
            self._device.button(
                target.button,
                "press" if target.pressed else "release",
                target.route.source,
                target.route.ttl_ms,
                target.route.controller,
            )
            metadata = {"button": target.button, "pressed": target.pressed}
        elif command.kind is ActionKind.GAMEPAD_STICK and isinstance(target, GamepadStickTarget):
            prefix = "left" if target.stick == "left" else "right"
            self._device.set_axis(
                f"{prefix}_x",
                target.x,
                target.route.source,
                target.route.ttl_ms,
                target.route.controller,
            )
            self._device.set_axis(
                f"{prefix}_y",
                target.y,
                target.route.source,
                target.route.ttl_ms,
                target.route.controller,
            )
            metadata = {"stick": target.stick, "x": target.x, "y": target.y}
        elif command.kind is ActionKind.GAMEPAD_TRIGGER and isinstance(target, GamepadTriggerTarget):
            self._device.set_trigger(
                target.trigger,
                target.value,
                target.route.source,
                target.route.ttl_ms,
                target.route.controller,
            )
            metadata = {"trigger": target.trigger, "value": target.value}
        elif command.kind is ActionKind.GAMEPAD_RESET and isinstance(target, GamepadResetTarget):
            self._device.reset(target.route.controller)
            metadata = {"reset": True}
        else:
            raise ValueError("virtual gamepad adapter requires a gamepad action command")

        completed_at_ms = int(self._clock_ms())
        metadata.update(
            {
                "controller": target.route.controller,
                "source": target.route.source,
                "ttl_ms": target.route.ttl_ms,
            }
        )
        return ActionResult(
            executed=True,
            device_id=self._device_id,
            kind=command.kind,
            started_at_ms=started_at_ms,
            completed_at_ms=completed_at_ms,
            target=target,
            metadata=metadata,
        )
