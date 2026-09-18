from __future__ import annotations

import numpy as np
from PySide6.QtCore import Qt
from PySide6.QtGui import QBrush, QColor, QImage, QPainterPath, QPen, QPixmap

from .viewport_overlay import game_view_scene_rect, monitor_scene_rect


def cosmetic_pen(color, width: float = 1.0, style=Qt.SolidLine) -> QPen:
    """Create an overlay pen whose width stays readable while zooming."""
    pen = QPen(color, width, style)
    pen.setCosmetic(True)
    return pen


def create_map_scene_items(scene, view, nav_core) -> dict:
    map_img = nav_core.get_map_image()
    h, w, c = map_img.shape
    if not map_img.flags["C_CONTIGUOUS"]:
        map_img = np.ascontiguousarray(map_img)

    qimg = QImage(map_img.data, w, h, w * c, QImage.Format_RGB888)
    pixmap = QPixmap.fromImage(qimg)

    scene.clear()
    map_item = scene.addPixmap(pixmap)
    map_item.setZValue(0)

    player_item = scene.addEllipse(-6, -6, 12, 12, cosmetic_pen(QColor("#FF5D5D"), 2), QBrush(QColor("#FF5D5D")))
    player_item.setZValue(4)
    player_item.setVisible(False)

    target_pen = cosmetic_pen(QColor(0, 255, 0, 220), 2)
    path = QPainterPath()
    path.moveTo(-10, 0)
    path.lineTo(10, 0)
    path.moveTo(0, -10)
    path.lineTo(0, 10)
    target_item = scene.addPath(path, target_pen)
    target_item.setZValue(5)
    target_item.setVisible(False)

    green_pen = cosmetic_pen(QColor(0, 255, 0, 190), 2, Qt.DashLine)
    monitor_rect_item = scene.addRect(0, 0, 0, 0, green_pen)
    monitor_rect_item.setZValue(2)
    monitor_rect_item.setVisible(False)

    orange_pen = cosmetic_pen(QColor(255, 140, 0, 220), 2, Qt.DashLine)
    game_view_rect_item = scene.addRect(0, 0, 0, 0, orange_pen)
    game_view_rect_item.setZValue(2)
    game_view_rect_item.setVisible(False)

    if hasattr(view, "set_map_item"):
        view.set_map_item(map_item)
    else:
        view.fitInView(map_item, Qt.KeepAspectRatio)
    return {
        "map_item": map_item,
        "player_item": player_item,
        "target_item": target_item,
        "monitor_rect_item": monitor_rect_item,
        "game_view_rect_item": game_view_rect_item,
    }


def update_player_marker(scene, player_item, nav_core, global_pos):
    offset_x, offset_y = nav_core.crop_offset
    display_x = global_pos[0] - offset_x
    display_y = global_pos[1] - offset_y
    if not player_item:
        player_item = scene.addEllipse(-6, -6, 12, 12, cosmetic_pen(QColor("#FF5D5D"), 2), QBrush(QColor("#FF5D5D")))
        player_item.setZValue(2)
    player_item.setPos(display_x, display_y)
    player_item.setVisible(True)
    return player_item, display_x, display_y


def update_monitor_rect_item(monitor_rect_item, *, player_pos, capture_rect, player_local_pos, nav_core) -> None:
    if not monitor_rect_item or not player_pos or not nav_core:
        return
    rect = monitor_scene_rect(player_pos, capture_rect, player_local_pos, nav_core)
    if not rect:
        return
    monitor_rect_item.setRect(*rect)
    if not monitor_rect_item.isVisible():
        monitor_rect_item.setVisible(True)


def update_game_view_rect_item(game_view_rect_item, *, player_pos, nav_core, nav_config) -> None:
    if not game_view_rect_item or not player_pos or not nav_core or not nav_config:
        return
    rect = game_view_scene_rect(player_pos, nav_core, nav_config)
    if not rect:
        game_view_rect_item.setVisible(False)
        return
    game_view_rect_item.setRect(*rect)
    if not game_view_rect_item.isVisible():
        game_view_rect_item.setVisible(True)


def center_view_on_global_position(view, nav_core, global_pos) -> None:
    offset_x, offset_y = nav_core.crop_offset
    view.centerOn(global_pos[0] - offset_x, global_pos[1] - offset_y)


def update_localization_view(
    *,
    scene,
    view,
    player_item,
    nav_core,
    localization,
    capture_rect,
    player_local_pos,
    update_monitor_rect,
    update_game_view_rect,
):
    if localization.is_localized:
        player_item, display_x, display_y = update_player_marker(
            scene,
            player_item,
            nav_core,
            localization.localized_pos,
        )
        update_monitor_rect(localization.localized_pos, capture_rect=capture_rect, player_local_pos=player_local_pos)
        update_game_view_rect(localization.localized_pos)
        view.centerOn(display_x, display_y)
        return player_item

    fallback_pos = nav_core.last_good_pos or nav_core.drawing_saved_pos
    if fallback_pos:
        update_monitor_rect(
            fallback_pos,
            capture_rect=capture_rect,
            player_local_pos=player_local_pos,
        )
        update_game_view_rect(fallback_pos)
    hide_item(player_item)
    return player_item


def create_last_position_marker(scene, item, nav_core, global_pos):
    offset_x, offset_y = nav_core.crop_offset
    display_x = global_pos[0] - offset_x
    display_y = global_pos[1] - offset_y
    if not item:
        purple_color = QColor(128, 0, 128)
        item = scene.addEllipse(-5, -5, 10, 10, QPen(purple_color), QBrush(purple_color))
        item.setZValue(3)
    item.setPos(display_x, display_y)
    item.setVisible(True)
    return item


def create_initial_hint_marker(scene, item, scene_pos):
    if not item:
        blue_color = QColor("blue")
        item = scene.addEllipse(-5, -5, 10, 10, QPen(blue_color), QBrush(blue_color))
        item.setZValue(3)
    item.setPos(scene_pos)
    item.setVisible(True)
    return item


def set_target_marker(target_item, scene_pos) -> None:
    if not target_item:
        return
    target_item.setPos(scene_pos)
    target_item.setVisible(True)


def hide_item(item) -> None:
    if item:
        item.setVisible(False)
