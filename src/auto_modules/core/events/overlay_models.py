from __future__ import annotations

from dataclasses import dataclass


@dataclass
class EventOverlayModel:
    event_id: str
    event_type: str
    display_name: str
    global_pos: tuple[int, int]
    state: str
    priority: int
    color: str
    label: str


def task_to_overlay(task, definition=None) -> EventOverlayModel:
    display_name = getattr(definition, "display_name", task.event_type) if definition else task.event_type
    color = "#ffaa00"
    if str(task.state).endswith("RUNNING") or getattr(task.state, "value", task.state) == "running":
        color = "#00ff66"
    elif getattr(task.state, "value", task.state) in ("completed", "ignored"):
        color = "#777777"
    return EventOverlayModel(
        event_id=task.id,
        event_type=task.event_type,
        display_name=display_name,
        global_pos=task.global_pos,
        state=getattr(task.state, "value", str(task.state)),
        priority=int(task.priority),
        color=color,
        label=display_name,
    )

