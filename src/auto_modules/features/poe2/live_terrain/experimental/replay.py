"""Minimal deterministic replay contract for experiment evidence."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Iterable


@dataclass(frozen=True, slots=True)
class ReplayFrame:
    captured_at_ms: int
    payload: Any


@dataclass(frozen=True, slots=True)
class ReplayManifest:
    """Portable metadata identifying a deterministic evidence sequence."""

    replay_id: str
    map_instance_id: str | None = None
    scenario: str = "unknown"
    version: int = 1
    tags: tuple[str, ...] = field(default_factory=tuple)

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


class ReplaySource:
    def __init__(self, frames: Iterable[ReplayFrame], *, manifest: ReplayManifest | None = None) -> None:
        self._frames = tuple(frames)
        self.manifest = manifest

    def __iter__(self):
        return iter(self._frames)

    def __len__(self) -> int:
        return len(self._frames)

    def at(self, index: int) -> ReplayFrame:
        return self._frames[index]
