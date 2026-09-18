"""Concrete keyboard device backed by PyDirectInput."""

from __future__ import annotations


class PyDirectInputKeyboardDevice:
    """Deliver keyboard state through the configured PyDirectInput module."""

    def __init__(self, module=None) -> None:
        if module is None:
            import pydirectinput as module
        self._module = module

    def key_down(self, key: str) -> None:
        self._module.keyDown(key)

    def key_up(self, key: str) -> None:
        self._module.keyUp(key)
