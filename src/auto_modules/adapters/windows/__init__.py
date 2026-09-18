"""Windows platform adapters."""

from .hotkeys import HotkeyTriggerSource
from .window_finder import WindowInfo, find_game_window, primary_screen_rect, set_process_dpi_awareness

__all__ = [
    "HotkeyTriggerSource",
    "WindowInfo",
    "find_game_window",
    "primary_screen_rect",
    "set_process_dpi_awareness",
]
