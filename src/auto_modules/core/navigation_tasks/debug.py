from __future__ import annotations

from auto_modules.core.events.debug import event_log


def nav_log(message: str, **fields) -> None:
    event_log(message, **fields)

