"""Side-effect adapter contracts for the vision process."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


@dataclass(frozen=True, slots=True)
class CapturedFrame:
    generation: int
    sequence: int
    captured_at_ms: int
    map_instance: str
    payload: bytes


class FrameCapture(Protocol):
    def capture(self) -> CapturedFrame | None: ...


class FrameProcessor(Protocol):
    def process(self, frame: CapturedFrame) -> Any: ...
