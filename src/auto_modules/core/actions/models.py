"""Compatibility request type for the existing mapped-pointer proof."""

from __future__ import annotations

from dataclasses import dataclass

from auto_modules.core.spatial.desktop_mapping import MappedPoint

from .contracts import ActionKind, ActionResult


@dataclass(frozen=True)
class ActionRequest:
    """One desired action at an already mapped destination point."""

    kind: ActionKind
    point: MappedPoint
    interval_ms: int = 80

    def __post_init__(self) -> None:
        if not isinstance(self.kind, ActionKind):
            raise TypeError("kind must be an ActionKind")
        if self.kind not in (ActionKind.MOVE, ActionKind.DOUBLE_CLICK):
            raise ValueError("ActionRequest supports only mapped pointer action kinds")
        if not isinstance(self.point, MappedPoint):
            raise TypeError("point must be a MappedPoint")
        if not isinstance(self.interval_ms, int) or isinstance(self.interval_ms, bool) or self.interval_ms < 0:
            raise ValueError("interval_ms must be a non-negative integer")
