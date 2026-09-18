from __future__ import annotations

from typing import Callable

from PySide6.QtCore import QEvent, Qt


def handle_navigation_map_event_filter(
    *,
    watched,
    event,
    scene,
    handle_map_click: Callable[[object], None],
) -> bool:
    """Handle map scene mouse events before they reach the default Qt path."""
    if (
        watched == scene
        and event.type() == QEvent.GraphicsSceneMousePress
        and event.button() == Qt.LeftButton
    ):
        handle_map_click(event.scenePos())
        return True
    return False
