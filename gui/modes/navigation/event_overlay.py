from __future__ import annotations

from PySide6.QtGui import QBrush, QColor, QPen


def clear_event_overlay(scene, items: list) -> list:
    for item in items:
        try:
            scene.removeItem(item)
        except RuntimeError:
            pass
    return []


def global_to_scene(point, nav_core):
    if point is None or not nav_core:
        return None
    offset_x, offset_y = nav_core.crop_offset
    return point[0] - offset_x, point[1] - offset_y


def render_event_overlay(scene, nav_core, event_coordinator, items: list) -> list:
    if not scene or not nav_core or not event_coordinator:
        return clear_event_overlay(scene, items) if scene else []

    items = clear_event_overlay(scene, items)
    for overlay in event_coordinator.overlays():
        mapped = global_to_scene(overlay.global_pos, nav_core)
        if mapped is None:
            continue
        color = QColor(overlay.color)
        radius = 8 if overlay.state == "running" else 6
        marker = scene.addEllipse(
            mapped[0] - radius,
            mapped[1] - radius,
            radius * 2,
            radius * 2,
            QPen(color, 3),
            QBrush(QColor(color.red(), color.green(), color.blue(), 80)),
        )
        marker.setZValue(6)
        items.append(marker)

        label = scene.addText(f"{overlay.label} {overlay.state}")
        label.setDefaultTextColor(color)
        label.setPos(mapped[0] + radius + 4, mapped[1] - radius - 8)
        label.setZValue(6)
        items.append(label)
    return items

