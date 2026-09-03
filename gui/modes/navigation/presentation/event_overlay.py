from __future__ import annotations

from PySide6.QtCore import Qt
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
    _render_player_center_mask_overlay(scene, nav_core, event_coordinator, items)
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
            _cosmetic_pen(color, 3),
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


def _cosmetic_pen(color, width: float) -> QPen:
    pen = QPen(color, width)
    pen.setCosmetic(True)
    return pen


def _render_player_center_mask_overlay(scene, nav_core, event_coordinator, items: list) -> None:
    loot_config = _event_config(event_coordinator, "loot")
    if not loot_config:
        return
    if not bool(loot_config.get("enabled", True)):
        return
    if not bool(loot_config.get("player_center_mask_enabled", True)):
        return
    if not bool(loot_config.get("player_center_mask_overlay_enabled", True)):
        return

    player_pos = _player_global_pos(nav_core)
    mapped = global_to_scene(player_pos, nav_core)
    if mapped is None:
        return

    radius = max(1.0, float(loot_config.get("player_center_mask_radius", 28) or 28))
    scene_radius = radius * max(1e-6, float(getattr(nav_core, "draw_scale", 1.0) or 1.0))
    color = QColor(0, 190, 255, 210)
    pen = QPen(color, 2, Qt.DashLine)
    brush = QBrush(QColor(color.red(), color.green(), color.blue(), 24))
    circle = scene.addEllipse(
        mapped[0] - scene_radius,
        mapped[1] - scene_radius,
        scene_radius * 2,
        scene_radius * 2,
        pen,
        brush,
    )
    circle.setZValue(5)
    items.append(circle)


def _event_config(event_coordinator, event_type: str) -> dict:
    config = getattr(event_coordinator, "config", None)
    if config is None:
        return {}
    if hasattr(config, "event"):
        value = config.event(event_type)
    else:
        value = ((getattr(config, "events", {}) or {}).get(event_type) or {})
    return value if isinstance(value, dict) else {}


def _player_global_pos(nav_core):
    for name in ("current_pos", "last_good_pos", "drawing_saved_pos"):
        value = getattr(nav_core, name, None)
        if value is not None:
            return value
    return None
