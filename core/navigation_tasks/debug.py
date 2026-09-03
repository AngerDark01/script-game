from __future__ import annotations

from core.events.debug import event_log


def nav_log(message: str, **fields) -> None:
    event_log(message, **fields)

