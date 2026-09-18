from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


EVENT_HOOK_VISIBLE_TARGET = "event_visible_target"
EVENT_HOOK_COMPLETED = "event_completed"
EVENT_HOOK_NAMES = (EVENT_HOOK_VISIBLE_TARGET, EVENT_HOOK_COMPLETED)
EVENT_HOOK_LABELS = {
    EVENT_HOOK_VISIBLE_TARGET: "事件进入真实视野",
    EVENT_HOOK_COMPLETED: "事件完成之后",
}


@dataclass(frozen=True)
class EventHookContext:
    """Immutable payload passed to event hook handlers."""

    hook_name: str
    now_ms: int
    navigation_task_id: str | None = None
    event_task_id: str | None = None
    event_type: str = ""
    event_global_pos: tuple[int, int] | None = None
    player_global_pos: tuple[float, float] | None = None
    reason: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
