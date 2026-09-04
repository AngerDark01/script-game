"""Device-neutral requests and results for actions at already mapped points."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from types import MappingProxyType
from typing import Any, Mapping

from core.spatial.desktop_mapping import MappedPoint


class ActionKind(StrEnum):
    """Pointer actions currently supported by generic action adapters."""

    MOVE = "move"
    DOUBLE_CLICK = "double_click"


@dataclass(frozen=True)
class ActionRequest:
    """One desired action at an already mapped destination point."""

    kind: ActionKind
    point: MappedPoint
    interval_ms: int = 80

    def __post_init__(self) -> None:
        if not isinstance(self.kind, ActionKind):
            raise TypeError("kind must be an ActionKind")
        if not isinstance(self.point, MappedPoint):
            raise TypeError("point must be a MappedPoint")
        if not isinstance(self.interval_ms, int) or isinstance(self.interval_ms, bool) or self.interval_ms < 0:
            raise ValueError("interval_ms must be a non-negative integer")


@dataclass(frozen=True)
class ActionResult:
    """Observable outcome from an action adapter, including exact executed point."""

    executed: bool
    point: tuple[int, int]
    device_id: str
    kind: ActionKind
    started_at_ms: int
    completed_at_ms: int
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if len(self.point) != 2:
            raise ValueError("point must contain two coordinates")
        object.__setattr__(self, "point", (int(self.point[0]), int(self.point[1])))
        if not self.device_id:
            raise ValueError("device_id must not be empty")
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))
