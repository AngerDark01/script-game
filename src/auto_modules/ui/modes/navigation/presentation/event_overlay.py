from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import Qt
from PySide6.QtGui import QBrush, QColor, QPen


@dataclass(frozen=True)
class EventOverlayContext:
    """Domain-neutral values exposed to optional overlay providers."""

    event_config: object
    player_global_pos: tuple[float, float] | None
    draw_scale: float


@dataclass(frozen=True)
class EventCircleOverlay:
    """A circle described in global-position and scene-radius coordinates."""

    global_pos: tuple[float, float]
    scene_radius: float
    color: str = "#00beff"
    line_width: float = 2.0
    fill_alpha: int = 24
    dashed: bool = True
    z_value: float = 5.0


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


def render_event_overlay(
    scene,
    nav_core,
    event_coordinator,
    items: list,
    *,
    overlay_providers=(),
) -> list:
    if not scene or not nav_core or not event_coordinator:
        return clear_event_overlay(scene, items) if scene else []

    items = clear_event_overlay(scene, items)
    context = EventOverlayContext(
        event_config=getattr(event_coordinator, "config", None),
        player_global_pos=_player_global_pos(nav_core),
        draw_scale=max(1e-6, float(getattr(nav_core, "draw_scale", 1.0) or 1.0)),
    )
    for provider in overlay_providers:
        for overlay in provider(context) or ():
            _render_circle_overlay(scene, nav_core, overlay, items)
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


def _render_circle_overlay(scene, nav_core, overlay: EventCircleOverlay, items: list) -> None:
    mapped = global_to_scene(overlay.global_pos, nav_core)
    if mapped is None:
        return

    scene_radius = max(1.0, float(overlay.scene_radius))
    color = QColor(overlay.color)
    color.setAlpha(210)
    pen_style = Qt.DashLine if overlay.dashed else Qt.SolidLine
    pen = QPen(color, float(overlay.line_width), pen_style)
    brush = QBrush(QColor(color.red(), color.green(), color.blue(), int(overlay.fill_alpha)))
    circle = scene.addEllipse(
        mapped[0] - scene_radius,
        mapped[1] - scene_radius,
        scene_radius * 2,
        scene_radius * 2,
        pen,
        brush,
    )
    circle.setZValue(float(overlay.z_value))
    items.append(circle)


def _player_global_pos(nav_core):
    for name in ("current_pos", "last_good_pos", "drawing_saved_pos"):
        value = getattr(nav_core, name, None)
        if value is not None:
            return value
    return None
