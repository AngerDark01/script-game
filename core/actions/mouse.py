"""Mouse implementation of generic mapped-point actions."""

from __future__ import annotations

import time
from typing import Callable, Protocol

from core.perception.models import CoordinateSpace

from .contracts import ActionCommand, ActionKind, ActionResult, PointerTarget
from .models import ActionRequest


class MouseDevice(Protocol):
    """The minimal platform mouse capability needed by this adapter."""

    def move_to(self, x: int, y: int) -> bool | None: ...

    def mouse_down(self, button: str = "left") -> None: ...

    def mouse_up(self, button: str = "left") -> None: ...


class ActionExecutionError(RuntimeError):
    """Raised when a mapped action cannot be delivered to its input device."""


class MouseActionAdapter:
    """Deliver mouse actions without accepting perception or mapping-policy objects."""

    def __init__(
        self,
        *,
        device: MouseDevice,
        clock_ms: Callable[[], int] | None = None,
        sleep: Callable[[float], None] | None = None,
        device_id: str = "mouse",
    ) -> None:
        if not device_id.strip():
            raise ValueError("device_id must not be empty")
        self._device = device
        self._clock_ms = clock_ms or (lambda: int(time.monotonic() * 1000))
        self._sleep = sleep or time.sleep
        self._device_id = device_id

    def execute(self, request: ActionRequest | ActionCommand) -> ActionResult:
        """Move to a validated physical point, then optionally perform one double click."""
        command = _as_pointer_command(request)
        target = command.target
        if not isinstance(target, PointerTarget):
            raise ValueError("mouse actions require a PointerTarget")
        if target.point.destination_space is not CoordinateSpace.PHYSICAL_SCREEN:
            raise ValueError("mouse actions require a PHYSICAL_SCREEN mapped point")
        x = int(round(target.point.destination_point.x))
        y = int(round(target.point.destination_point.y))
        started_at_ms = int(self._clock_ms())
        moved = self._device.move_to(x, y)
        if moved is False:
            raise ActionExecutionError(f"mouse device could not move to ({x}, {y})")

        click_count = 0
        if command.kind is ActionKind.DOUBLE_CLICK:
            self._click_once()
            self._sleep(command.interval_ms / 1000.0)
            self._click_once()
            click_count = 2
        elif command.kind is not ActionKind.MOVE:
            raise ValueError(f"unsupported mouse action kind: {command.kind}")

        completed_at_ms = int(self._clock_ms())
        return ActionResult(
            executed=True,
            device_id=self._device_id,
            kind=command.kind,
            started_at_ms=started_at_ms,
            completed_at_ms=completed_at_ms,
            point=(x, y),
            target=target,
            metadata={
                "click_count": click_count,
                "source_space": target.point.source_space.value,
                "destination_space": target.point.destination_space.value,
                "mapping": dict(target.point.metadata),
            },
        )

    def _click_once(self) -> None:
        self._device.mouse_down("left")
        self._device.mouse_up("left")


def _as_pointer_command(request: ActionRequest | ActionCommand) -> ActionCommand:
    if isinstance(request, ActionRequest):
        return ActionCommand(
            kind=request.kind,
            target=PointerTarget(request.point),
            interval_ms=request.interval_ms,
        )
    if isinstance(request, ActionCommand):
        return request
    raise TypeError("request must be an ActionRequest or ActionCommand")
