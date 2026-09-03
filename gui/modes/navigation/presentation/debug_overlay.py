from __future__ import annotations

from .viewport_overlay import screen_overlay_geometry


def update_debug_overlay(overlay, *, capture_rect: dict | None, nav_config, scale: tuple[float, float]) -> bool:
    """Update the transparent screen overlay; return True when it is shown."""
    if overlay is None:
        return False
    rect, anchor = screen_overlay_geometry(capture_rect, nav_config, scale)
    if not rect:
        overlay.hide_overlay()
        return False
    overlay.set_rect_and_show(
        rect["left"],
        rect["top"],
        rect["width"],
        rect["height"],
        anchor=anchor,
    )
    return True
