"""Minimal deterministic replay contract for experiment evidence."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable


@dataclass(frozen=True, slots=True)
class ReplayFrame:
    captured_at_ms: int
    payload: Any


class ReplaySource:
    def __init__(self, frames: Iterable[ReplayFrame]) -> None:
        self._frames = tuple(frames)

    def __iter__(self):
        return iter(self._frames)

    def __len__(self) -> int:
        return len(self._frames)
