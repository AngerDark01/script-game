"""Input mapping and platform input adapters."""

from .click_diagnostics import (
    collect_window_diagnostics,
    focus_window_at,
    format_window_info,
    win_cursor_pos,
)
from .click_executor import fallback_pydirect_click, send_click
from .click_pipeline import execute_click
from .controller import MotionController
from .motion_mapping import (
    ClickMappingResult,
    apply_bottom_click_guard,
    calculate_mapped_target_click,
    calculate_movement_click,
)
from .screen_bounds import clamp_screen_pos, screen_height_from_driver_or_size

try:
    from .win32_driver import InputDriver, RECT
except Exception:  # pragma: no cover - non-Windows import fallback
    InputDriver = None
    RECT = None

__all__ = [
    "ClickMappingResult",
    "InputDriver",
    "MotionController",
    "RECT",
    "apply_bottom_click_guard",
    "calculate_mapped_target_click",
    "calculate_movement_click",
    "clamp_screen_pos",
    "collect_window_diagnostics",
    "fallback_pydirect_click",
    "focus_window_at",
    "format_window_info",
    "execute_click",
    "screen_height_from_driver_or_size",
    "send_click",
    "win_cursor_pos",
]
