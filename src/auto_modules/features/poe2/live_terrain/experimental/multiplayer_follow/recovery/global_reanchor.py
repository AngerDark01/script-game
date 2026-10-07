"""Final asynchronous recovery backend for continuous follow.

The backend owns the legacy global worker callback so the live page never
decides to start a global registration directly.  This keeps the recovery
policy side-effect free and makes the final fallback observable/testable.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True)
class GlobalReanchorRequest:
    reason: str
    preserve_follow: bool = True


class GlobalReanchorBackend:
    def __init__(self, starter: Callable[..., None]) -> None:
        self._starter = starter
        self.started = 0

    def start(self, reason: str, *, preserve_follow: bool = True) -> GlobalReanchorRequest:
        request = GlobalReanchorRequest(str(reason), bool(preserve_follow))
        self.started += 1
        if request.preserve_follow:
            self._starter(recovery=True, preserve_follow=True)
        else:
            self._starter(recovery=True)
        return request


__all__ = ["GlobalReanchorBackend", "GlobalReanchorRequest"]
