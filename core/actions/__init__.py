"""Device-neutral action commands and concrete input adapters."""

from .contracts import (
    ActionAdapter,
    ActionCommand,
    ActionKind,
    ActionResult,
    ActionTarget,
    GamepadButtonTarget,
    GamepadResetTarget,
    GamepadStickTarget,
    GamepadTriggerTarget,
    KeyboardTarget,
    PointerTarget,
    VirtualControllerRoute,
)
from .gamepad import VirtualGamepadActionAdapter, VirtualGamepadDevice
from .keyboard import KeyboardActionAdapter, KeyboardDevice, PyDirectInputKeyboardDevice
from .models import ActionRequest
from .mouse import ActionExecutionError, MouseActionAdapter, MouseDevice

__all__ = [
    "ActionExecutionError",
    "ActionAdapter",
    "ActionCommand",
    "ActionKind",
    "ActionRequest",
    "ActionResult",
    "ActionTarget",
    "GamepadButtonTarget",
    "GamepadResetTarget",
    "GamepadStickTarget",
    "GamepadTriggerTarget",
    "KeyboardActionAdapter",
    "KeyboardDevice",
    "KeyboardTarget",
    "MouseActionAdapter",
    "MouseDevice",
    "PointerTarget",
    "PyDirectInputKeyboardDevice",
    "VirtualControllerRoute",
    "VirtualGamepadActionAdapter",
    "VirtualGamepadDevice",
]
