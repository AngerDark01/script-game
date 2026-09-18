"""Navigation-domain intent translation into typed composition actions."""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite

from auto_modules.core.actions import ActionCommand, ActionKind, KeyboardTarget, PointerTarget
from auto_modules.core.navigation_tasks.models import NavigationIntentType
from auto_modules.core.spatial import physical_screen_point


@dataclass(frozen=True)
class MapMovementAction:
    """A stitched-global-map request that must use navigation spatial policy."""

    player_position: tuple[float, float]
    target_position: tuple[float, float]
    force_click_target: bool = False
    reason: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "player_position", _finite_point(self.player_position, "player_position"))
        object.__setattr__(self, "target_position", _finite_point(self.target_position, "target_position"))
        if not isinstance(self.force_click_target, bool):
            raise TypeError("force_click_target must be a bool")
        if not isinstance(self.reason, str):
            raise TypeError("reason must be a string")


@dataclass(frozen=True)
class PrimitiveNavigationAction:
    """One primitive device command with navigation audit context."""

    command: ActionCommand
    reason: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.command, ActionCommand):
            raise TypeError("command must be an ActionCommand")
        if not isinstance(self.reason, str):
            raise TypeError("reason must be a string")


def translate_navigation_intent(intent) -> MapMovementAction | PrimitiveNavigationAction | None:
    """Translate only executable navigation intents; absent payloads remain no-ops."""
    if intent is None or intent.type in (NavigationIntentType.NONE, NavigationIntentType.WAIT):
        return None
    metadata = getattr(intent, "metadata", None) or {}
    reason = str(getattr(intent, "message", "") or "")

    if intent.type is NavigationIntentType.MOVE_MAP:
        if not intent.player_pos or not intent.subgoal:
            return None
        try:
            return MapMovementAction(
                player_position=intent.player_pos,
                target_position=intent.subgoal,
                force_click_target=bool(metadata.get("force_click_target")),
                reason=reason,
            )
        except (TypeError, ValueError):
            return None

    if intent.type is NavigationIntentType.CLICK_SCREEN:
        screen_pos = metadata.get("screen_pos")
        try:
            return PrimitiveNavigationAction(
                command=ActionCommand(
                    ActionKind.CLICK,
                    PointerTarget(physical_screen_point(screen_pos[0], screen_pos[1])),
                ),
                reason=reason or "navigation_event_click",
            )
        except (IndexError, KeyError, TypeError, ValueError):
            return None

    if intent.type is NavigationIntentType.PRESS_KEY:
        key = metadata.get("key")
        try:
            return PrimitiveNavigationAction(
                command=ActionCommand(ActionKind.KEY_CHORD, KeyboardTarget((key,))),
                reason=reason or "navigation_event_key",
            )
        except (TypeError, ValueError):
            return None

    return None


def _finite_point(value, name: str) -> tuple[float, float]:
    try:
        x, y = value
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must contain exactly two coordinates") from exc
    point = float(x), float(y)
    if not all(isfinite(component) for component in point):
        raise ValueError(f"{name} coordinates must be finite")
    return point
