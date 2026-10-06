"""Domain-neutral follow orchestration around the shared motion runtime."""

from __future__ import annotations

from typing import Any


class FollowController:
    """Keep target refresh and runtime ticking in one reusable boundary.

    The injected runtime remains the single path planner/output decision source;
    this controller only coordinates target updates and exposes observations.
    """

    def __init__(self, runtime: Any, target_source: Any) -> None:
        self.runtime = runtime
        self.target_source = target_source
        self.running = False

    def start(self) -> None:
        self.running = True

    def stop(self) -> None:
        self.running = False

    def tick(self, *, now_ms: int) -> Any:
        if not self.running:
            return {}
        refresh = getattr(self.runtime, "refresh_simulated_target", None)
        if callable(refresh):
            refresh(now_ms=now_ms)
        return self.runtime.tick(now_ms=now_ms)
