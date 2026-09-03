from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any

from .formatting import format_fields


_COORD_LOG_PATH = Path(__file__).resolve().parents[3] / "logs" / "coordinate_diagnostics.log"
_COORD_SESSION_STARTED = False


def coord_log(message: str, **fields: Any) -> None:
    """Write coordinate diagnostics to a dedicated file without console spam."""
    global _COORD_SESSION_STARTED
    suffix = format_fields(fields)
    timestamp = time.strftime("%H:%M:%S")
    millis = int((time.time() % 1) * 1000)
    line = f"[Coord {timestamp}.{millis:03d} pid={os.getpid()}] {message}{suffix}"
    _COORD_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    mode = "a" if _COORD_SESSION_STARTED else "w"
    with _COORD_LOG_PATH.open(mode, encoding="utf-8-sig") as handle:
        if not _COORD_SESSION_STARTED:
            handle.write(f"=== coordinate diagnostics session {time.strftime('%Y-%m-%d %H:%M:%S')} ===\n")
            _COORD_SESSION_STARTED = True
        handle.write(line + "\n")
    try:
        from core.events.debug import event_log

        event_log(f"coord {message}", **fields)
    except Exception:
        pass
