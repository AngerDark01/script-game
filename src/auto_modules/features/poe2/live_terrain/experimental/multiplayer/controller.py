"""Qt-free dual-motion worker boundary.

The UI page remains the compatibility façade for now.  This module owns only
generation/session filtering and event normalization; capture and tracking
implementations are injected by the caller.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class DualMotionEvent:
    kind: str
    generation: int
    payload: Any = None


class DualMotionFrameRouter:
    """Reject results from retired workers before they reach page state."""

    def __init__(self) -> None:
        self._generation = 0
        self._accepted_frames = 0

    @property
    def generation(self) -> int:
        return self._generation

    @property
    def accepted_frames(self) -> int:
        return self._accepted_frames

    def begin(self, generation: int) -> None:
        self._generation = int(generation)

    def accept(self, generation: int, frame: Any) -> DualMotionEvent | None:
        if int(generation) != self._generation or frame is None:
            return None
        self._accepted_frames += 1
        return DualMotionEvent("frame_ready", self._generation, frame)


class DualMotionController:
    """Small headless façade around a capture/tracking pair."""

    def __init__(self, capture: Any = None, tracker: Any = None) -> None:
        self.capture = capture
        self.tracker = tracker
        self.router = DualMotionFrameRouter()
        self.running = False

    def start(self, generation: int) -> DualMotionEvent:
        self.router.begin(generation)
        self.running = True
        return DualMotionEvent("started", int(generation))

    def stop(self, generation: int | None = None) -> DualMotionEvent:
        self.running = False
        return DualMotionEvent("stopped", self.router.generation if generation is None else int(generation))

    def publish(self, generation: int, frame: Any) -> DualMotionEvent | None:
        return self.router.accept(generation, frame)
