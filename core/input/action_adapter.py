"""Compatibility backend from generic primitive actions to MotionController."""

from __future__ import annotations

import time
from typing import Callable

from core.actions import ActionCommand, ActionKind, ActionResult, KeyboardTarget, PointerTarget
from core.perception.models import CoordinateSpace


class MotionControllerActionAdapter:
    """Execute primitive actions through the existing MotionController policy/backend."""

    def __init__(
        self,
        *,
        controller,
        clock_ms: Callable[[], int] | None = None,
        device_id: str = "motion_controller",
    ) -> None:
        if not device_id.strip():
            raise ValueError("device_id must not be empty")
        self._controller = controller
        self._clock_ms = clock_ms or (lambda: int(time.monotonic() * 1000))
        self._device_id = device_id

    def execute(self, command: ActionCommand, *, reason: str | None = None) -> ActionResult:
        """Delegate a physical click or one-key chord without bypassing legacy safeguards."""
        if not isinstance(command, ActionCommand):
            raise TypeError("command must be an ActionCommand")
        started_at_ms = int(self._clock_ms())

        if command.kind is ActionKind.CLICK:
            return self._execute_click(command, started_at_ms, reason)
        if command.kind is ActionKind.KEY_CHORD:
            return self._execute_key(command, started_at_ms, reason)
        raise ValueError("MotionControllerActionAdapter supports only CLICK and one-key KEY_CHORD")

    def _execute_click(
        self,
        command: ActionCommand,
        started_at_ms: int,
        reason: str | None,
    ) -> ActionResult:
        if not isinstance(command.target, PointerTarget):
            raise ValueError("CLICK requires a PointerTarget")
        point = command.target.point
        if point.destination_space is not CoordinateSpace.PHYSICAL_SCREEN:
            raise ValueError("CLICK requires a PHYSICAL_SCREEN mapped point")
        screen_pos = (
            int(round(point.destination_point.x)),
            int(round(point.destination_point.y)),
        )
        effective_reason = reason or "navigation_primitive_click"
        legacy_result = self._controller.click_screen_position(screen_pos, reason=effective_reason)
        return ActionResult(
            executed=legacy_result is not None,
            device_id=self._device_id,
            kind=command.kind,
            started_at_ms=started_at_ms,
            completed_at_ms=int(self._clock_ms()),
            point=screen_pos,
            target=command.target,
            metadata={"reason": effective_reason, "legacy_executed": legacy_result is not None},
        )

    def _execute_key(
        self,
        command: ActionCommand,
        started_at_ms: int,
        reason: str | None,
    ) -> ActionResult:
        if not isinstance(command.target, KeyboardTarget) or len(command.target.keys) != 1:
            raise ValueError("KEY_CHORD requires exactly one KeyboardTarget key")
        key = command.target.keys[0]
        effective_reason = reason or "navigation_primitive_key"
        legacy_result = self._controller.press_key(key, reason=effective_reason)
        return ActionResult(
            executed=legacy_result is not None,
            device_id=self._device_id,
            kind=command.kind,
            started_at_ms=started_at_ms,
            completed_at_ms=int(self._clock_ms()),
            target=command.target,
            metadata={"reason": effective_reason, "legacy_executed": legacy_result is not None},
        )
