"""Windows platform adapters."""

from .hotkeys import HotkeyTriggerSource
from .window_finder import (
    WindowInfo,
    find_game_window,
    find_process_window,
    foreground_window_pid,
    is_process_foreground,
    primary_screen_rect,
    set_process_dpi_awareness,
)

__all__ = [
    "HotkeyTriggerSource",
    "WindowInfo",
    "find_game_window",
    "find_process_window",
    "foreground_window_pid",
    "is_process_foreground",
    "primary_screen_rect",
    "set_process_dpi_awareness",
]
