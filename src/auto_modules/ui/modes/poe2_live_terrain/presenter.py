"""Pure-ish presentation adapter for an in-memory terrain snapshot."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import numpy as np
import cv2
from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QImage, QPixmap, QPainter, QPen, QColor

if TYPE_CHECKING:
    from auto_modules.features.poe2.live_terrain import TerrainSnapshot


@dataclass(frozen=True)
class TerrainDisplay:
    pixmap: QPixmap
    metadata_lines: tuple[str, ...]


def terrain_pixmap(snapshot: TerrainSnapshot) -> QPixmap:
    """Render the live grid in the established stitched-map visual style.

    The producer's ``cell_state`` is a terrain classification, while the old
    visual map uses a dark explored surface and bright wall pixels. Unknown
    cells remain black so they cannot be mistaken for captured geometry.
    """
    height, width = snapshot.cell_state.shape
    rgb = np.empty((height, width, 3), dtype=np.uint8)
    rgb[:, :] = (0, 0, 0)
    walkable = (snapshot.cell_state == 1) & (snapshot.known_mask > 0)
    rgb[walkable] = (60, 60, 60)

    # The producer classifies the complete rectangular buffer, including the
    # blocked space outside rooms. Derive the legacy white wall look from the
    # boundary of walkable cells instead of painting every blocked cell white.
    walkable_padded = np.pad(walkable, 1, mode="constant", constant_values=False)
    kernel = np.ones((3, 3), dtype=np.uint8)
    dilated = cv2.dilate(walkable_padded.astype(np.uint8), kernel)[1:-1, 1:-1] > 0
    eroded = cv2.erode(walkable_padded.astype(np.uint8), kernel)[1:-1, 1:-1] > 0
    edge = dilated & ~eroded
    rgb[edge] = (235, 235, 235)
    image = QImage(
        rgb.data,
        width,
        height,
        width * 3,
        QImage.Format_RGB888,
    ).copy()
    return QPixmap.fromImage(image)


def present_snapshot(snapshot: TerrainSnapshot) -> TerrainDisplay:
    metadata = snapshot.metadata
    return TerrainDisplay(
        pixmap=terrain_pixmap(snapshot),
        metadata_lines=(
            f"区域：{metadata.area_id}",
            f"实例：{metadata.instance_id}",
            f"尺寸：{metadata.width} × {metadata.height}",
            f"抓取：{metadata.captured_at}",
            f"完整性：{metadata.raw_sha256 or '已通过结构校验'}",
        ),
    )


def present_localization_overlay(base_pixmap: QPixmap, state) -> QPixmap:
    """Draw one runtime position and its confirmed trail on a map copy."""
    if base_pixmap is None or base_pixmap.isNull():
        return QPixmap()
    result = QPixmap(base_pixmap)
    painter = QPainter(result)
    try:
        trail = tuple(getattr(state, "trajectory", ()) or ())
        if len(trail) >= 2:
            painter.setPen(QPen(QColor(255, 196, 0), max(2, result.width() // 1200)))
            for first, second in zip(trail, trail[1:]):
                painter.drawLine(QPointF(float(first[0]), float(first[1])), QPointF(float(second[0]), float(second[1])))
        position = getattr(state, "position", None)
        if position is not None:
            painter.setPen(QPen(QColor(20, 230, 120), max(2, result.width() // 900)))
            radius = max(4, result.width() // 350)
            painter.drawEllipse(QPointF(float(position[0]), float(position[1])), radius, radius)
    finally:
        painter.end()
    return result


def frame_pixmap(frame) -> QPixmap:
    """Convert a BGR/gray numpy frame to a detached Qt pixmap."""
    if frame is None:
        return QPixmap()
    if isinstance(frame, QPixmap):
        return QPixmap(frame)
    if hasattr(frame, "toImage"):
        return QPixmap.fromImage(frame.toImage())
    array = np.asarray(frame)
    if array.size == 0 or array.ndim not in (2, 3):
        return QPixmap()
    if array.ndim == 2:
        image = QImage(array.data, array.shape[1], array.shape[0], array.strides[0], QImage.Format_Grayscale8)
    elif array.shape[2] == 4:
        image = QImage(array.data, array.shape[1], array.shape[0], array.strides[0], QImage.Format_RGBA8888)
    else:
        image = QImage(array.data, array.shape[1], array.shape[0], array.strides[0], QImage.Format_BGR888)
    return QPixmap.fromImage(image.copy())
