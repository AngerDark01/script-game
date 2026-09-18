"""Edge-triggered Windows hotkey input behind an injectable reader."""

from __future__ import annotations

import os
from threading import Lock
from typing import Callable, Iterable


_VK_CODES = {
    **{chr(code): code for code in range(ord("A"), ord("Z") + 1)},
    **{f"F{index}": 0x6F + index for index in range(1, 13)},
    "SPACE": 0x20,
    "UP": 0x26,
    "DOWN": 0x28,
    "LEFT": 0x25,
    "RIGHT": 0x27,
}


def _windows_key_state(virtual_key: int) -> bool:
    if os.name != "nt":
        raise RuntimeError("default hotkey input requires Windows")
    import ctypes

    return bool(ctypes.windll.user32.GetAsyncKeyState(virtual_key) & 0x8000)


class HotkeyTriggerSource:
    def __init__(self, key_state: Callable[[int], bool] | None = None) -> None:
        self._key_state = key_state or _windows_key_state
        self._pressed: set[str] = set()
        self._lock = Lock()

    def poll(self, keys: Iterable[str]) -> tuple[str, ...]:
        normalized = tuple(dict.fromkeys(str(key or "").strip().upper() for key in keys))
        emitted: list[str] = []
        with self._lock:
            for key in normalized:
                virtual_key = _VK_CODES.get(key)
                if virtual_key is None:
                    continue
                pressed = bool(self._key_state(virtual_key))
                if pressed and key not in self._pressed:
                    emitted.append(key)
                if pressed:
                    self._pressed.add(key)
                else:
                    self._pressed.discard(key)
        return tuple(emitted)
