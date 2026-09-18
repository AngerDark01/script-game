"""Immutable, device-neutral action commands and adapter contracts."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from types import MappingProxyType
from typing import Any, Mapping, Protocol

from auto_modules.core.spatial.desktop_mapping import MappedPoint


class ActionKind(StrEnum):
    """The primitive actions understood by the initial device adapters."""

    MOVE = "move"
    CLICK = "click"
    DOUBLE_CLICK = "double_click"
    KEY_DOWN = "key_down"
    KEY_UP = "key_up"
    KEY_CHORD = "key_chord"
    GAMEPAD_BUTTON = "gamepad_button"
    GAMEPAD_STICK = "gamepad_stick"
    GAMEPAD_TRIGGER = "gamepad_trigger"
    GAMEPAD_RESET = "gamepad_reset"


@dataclass(frozen=True)
class ActionTarget:
    """Marker base type for validated device-specific command payloads."""


@dataclass(frozen=True)
class PointerTarget(ActionTarget):
    """A previously mapped desktop point for pointer actions."""

    point: MappedPoint

    def __post_init__(self) -> None:
        if not isinstance(self.point, MappedPoint):
            raise TypeError("point must be a MappedPoint")


@dataclass(frozen=True)
class KeyboardTarget(ActionTarget):
    """One key or an ordered key chord."""

    keys: tuple[str, ...]

    def __post_init__(self) -> None:
        if isinstance(self.keys, str):
            raw_keys = (self.keys,)
        else:
            try:
                raw_keys = tuple(self.keys)
            except TypeError as exc:
                raise TypeError("keys must be an iterable of strings") from exc
        if not raw_keys:
            raise ValueError("keys must contain at least one key")
        if any(not isinstance(key, str) or not key.strip() for key in raw_keys):
            raise ValueError("every keyboard key must be a non-empty string")
        normalized = tuple(key.strip().lower() for key in raw_keys)
        if len(set(normalized)) != len(normalized):
            raise ValueError("keyboard keys must not repeat")
        object.__setattr__(self, "keys", normalized)


@dataclass(frozen=True)
class VirtualControllerRoute:
    """Address and expiry policy for one independent virtual Xbox controller."""

    controller: int = 1
    source: str = "actions"
    ttl_ms: int = 250

    def __post_init__(self) -> None:
        if not isinstance(self.controller, int) or isinstance(self.controller, bool) or self.controller not in (1, 2):
            raise ValueError("controller must be either 1 or 2")
        if not isinstance(self.source, str) or not self.source.strip():
            raise ValueError("source must be a non-empty string")
        if not isinstance(self.ttl_ms, int) or isinstance(self.ttl_ms, bool) or self.ttl_ms <= 0:
            raise ValueError("ttl_ms must be a positive integer")
        object.__setattr__(self, "source", self.source.strip())


@dataclass(frozen=True)
class GamepadButtonTarget(ActionTarget):
    route: VirtualControllerRoute
    button: str
    pressed: bool = True

    def __post_init__(self) -> None:
        _require_route(self.route)
        if not isinstance(self.button, str) or not self.button.strip():
            raise ValueError("button must be a non-empty string")
        if not isinstance(self.pressed, bool):
            raise TypeError("pressed must be a bool")
        object.__setattr__(self, "button", self.button.strip())


@dataclass(frozen=True)
class GamepadStickTarget(ActionTarget):
    route: VirtualControllerRoute
    stick: str
    x: int
    y: int

    def __post_init__(self) -> None:
        _require_route(self.route)
        stick = _normalized_stick(self.stick)
        _require_axis("x", self.x)
        _require_axis("y", self.y)
        object.__setattr__(self, "stick", stick)


@dataclass(frozen=True)
class GamepadTriggerTarget(ActionTarget):
    route: VirtualControllerRoute
    trigger: str
    value: int

    def __post_init__(self) -> None:
        _require_route(self.route)
        trigger = _normalized_trigger(self.trigger)
        if not isinstance(self.value, int) or isinstance(self.value, bool) or not 0 <= self.value <= 255:
            raise ValueError("trigger value must be an integer between 0 and 255")
        object.__setattr__(self, "trigger", trigger)


@dataclass(frozen=True)
class GamepadResetTarget(ActionTarget):
    route: VirtualControllerRoute

    def __post_init__(self) -> None:
        _require_route(self.route)


@dataclass(frozen=True)
class ActionCommand:
    """One validated, device-neutral primitive action."""

    kind: ActionKind
    target: ActionTarget
    interval_ms: int = 80

    def __post_init__(self) -> None:
        if not isinstance(self.kind, ActionKind):
            raise TypeError("kind must be an ActionKind")
        if not isinstance(self.target, ActionTarget):
            raise TypeError("target must be an ActionTarget")
        if not isinstance(self.interval_ms, int) or isinstance(self.interval_ms, bool) or self.interval_ms < 0:
            raise ValueError("interval_ms must be a non-negative integer")
        expected_target = {
            ActionKind.MOVE: PointerTarget,
            ActionKind.CLICK: PointerTarget,
            ActionKind.DOUBLE_CLICK: PointerTarget,
            ActionKind.KEY_DOWN: KeyboardTarget,
            ActionKind.KEY_UP: KeyboardTarget,
            ActionKind.KEY_CHORD: KeyboardTarget,
            ActionKind.GAMEPAD_BUTTON: GamepadButtonTarget,
            ActionKind.GAMEPAD_STICK: GamepadStickTarget,
            ActionKind.GAMEPAD_TRIGGER: GamepadTriggerTarget,
            ActionKind.GAMEPAD_RESET: GamepadResetTarget,
        }[self.kind]
        if not isinstance(self.target, expected_target):
            raise ValueError(f"{self.kind.value} requires a {expected_target.__name__}")
        if self.kind in (ActionKind.KEY_DOWN, ActionKind.KEY_UP) and len(self.target.keys) != 1:
            raise ValueError(f"{self.kind.value} requires exactly one key")


@dataclass(frozen=True)
class ActionResult:
    """Observable result from a concrete action adapter."""

    executed: bool
    device_id: str
    kind: ActionKind
    started_at_ms: int
    completed_at_ms: int
    point: tuple[int, int] | None = None
    target: ActionTarget | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.executed, bool):
            raise TypeError("executed must be a bool")
        if not isinstance(self.kind, ActionKind):
            raise TypeError("kind must be an ActionKind")
        if not isinstance(self.device_id, str) or not self.device_id.strip():
            raise ValueError("device_id must not be empty")
        if not isinstance(self.started_at_ms, int) or not isinstance(self.completed_at_ms, int):
            raise TypeError("timestamps must be integers")
        if self.point is not None:
            if len(self.point) != 2:
                raise ValueError("point must contain two coordinates")
            object.__setattr__(self, "point", (int(self.point[0]), int(self.point[1])))
        if self.target is not None and not isinstance(self.target, ActionTarget):
            raise TypeError("target must be an ActionTarget")
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))


class ActionAdapter(Protocol):
    """A device adapter for one or more validated action commands."""

    def execute(self, command: ActionCommand) -> ActionResult: ...


def _require_route(route: VirtualControllerRoute) -> None:
    if not isinstance(route, VirtualControllerRoute):
        raise TypeError("route must be a VirtualControllerRoute")


def _normalized_stick(value: str) -> str:
    if not isinstance(value, str):
        raise TypeError("stick must be a string")
    normalized = value.strip().lower()
    if normalized not in ("left", "right"):
        raise ValueError("stick must be left or right")
    return normalized


def _normalized_trigger(value: str) -> str:
    if not isinstance(value, str):
        raise TypeError("trigger must be a string")
    normalized = value.strip().lower()
    aliases = {"left": "left", "lt": "left", "right": "right", "rt": "right"}
    if normalized not in aliases:
        raise ValueError("trigger must be left/lt or right/rt")
    return aliases[normalized]


def _require_axis(name: str, value: int) -> None:
    if not isinstance(value, int) or isinstance(value, bool) or not -32768 <= value <= 32767:
        raise ValueError(f"{name} must be an integer between -32768 and 32767")
