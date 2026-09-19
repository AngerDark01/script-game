"""Device-neutral position and event records shared between peers."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SharedPosition:
    device_id: str
    actor_id: str
    map_id: str
    map_version: str
    position: tuple[float, float]
    confidence: float
    captured_at_ms: int
    session_id: str = ""


@dataclass(frozen=True)
class SharedEvent:
    device_id: str
    event_id: str
    name: str
    targets: tuple[str, ...]
    deadline_ms: int
    session_id: str = ""


__all__ = ["SharedEvent", "SharedPosition"]
