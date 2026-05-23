from __future__ import annotations

import cv2
from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QPixmap, QPainter, QColor, QPen


def pixmap_from_image(image, fallback_image=None) -> QPixmap:
    source = image if image is not None else fallback_image
    if len(source.shape) == 2:
        height, width = source.shape
        q_image = QImage(source.data, width, height, width, QImage.Format_Grayscale8)
    else:
        rgb = cv2.cvtColor(source, cv2.COLOR_BGR2RGB)
        height, width, channels = rgb.shape
        q_image = QImage(rgb.data, width, height, channels * width, QImage.Format_RGB888)
    return QPixmap.fromImage(q_image)


def draw_sample_markers(
    pixmap: QPixmap,
    *,
    original_width: int,
    original_height: int,
    zoom: float,
    wall_points,
    player_points,
) -> QPixmap:
    target_w = int(original_width * zoom)
    target_h = int(original_height * zoom)
    scaled_pixmap = pixmap.scaled(target_w, target_h, Qt.KeepAspectRatio, Qt.SmoothTransformation)

    painter = QPainter(scaled_pixmap)
    pen_wall = QPen(QColor(52, 152, 219), 2)
    pen_player = QPen(QColor(46, 204, 113), 2)
    radius_outer = 5
    radius_inner = 2

    disp_w = scaled_pixmap.width()
    disp_h = scaled_pixmap.height()
    scale_x = disp_w / original_width
    scale_y = disp_h / original_height

    painter.setPen(pen_wall)
    for x, y in wall_points:
        dx = int(x * scale_x)
        dy = int(y * scale_y)
        painter.drawEllipse(dx - radius_outer, dy - radius_outer, radius_outer * 2, radius_outer * 2)
        painter.setBrush(QColor(52, 152, 219))
        painter.drawEllipse(dx - radius_inner, dy - radius_inner, radius_inner * 2, radius_inner * 2)
        painter.setBrush(Qt.NoBrush)

    painter.setPen(pen_player)
    for x, y in player_points:
        dx = int(x * scale_x)
        dy = int(y * scale_y)
        painter.drawEllipse(dx - radius_outer, dy - radius_outer, radius_outer * 2, radius_outer * 2)
        painter.setBrush(QColor(46, 204, 113))
        painter.drawEllipse(dx - radius_inner, dy - radius_inner, radius_inner * 2, radius_inner * 2)
        painter.setBrush(Qt.NoBrush)

    painter.end()
    return scaled_pixmap

