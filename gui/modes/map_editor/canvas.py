"""Interactive, zoomable canvas for reviewing and editing one wall layer."""

from __future__ import annotations

import math

import numpy as np
from PySide6.QtCore import QPointF, Qt, Signal
from PySide6.QtGui import QColor, QImage, QMouseEvent, QPainter, QWheelEvent
from PySide6.QtWidgets import QWidget


class WallEditorCanvas(QWidget):
    """Draw map layers and report map-space brush points without owning state."""

    stroke_started = Signal(tuple)
    stroke_extended = Signal(tuple)
    stroke_finished = Signal()
    zoom_changed = Signal(float)

    _MIN_ZOOM = 0.03
    _MAX_ZOOM = 32.0

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setMinimumSize(420, 320)
        self.setCursor(Qt.CursorShape.CrossCursor)
        self._base_array: np.ndarray | None = None
        self._add_array: np.ndarray | None = None
        self._erase_array: np.ndarray | None = None
        self._base_image: QImage | None = None
        self._add_image: QImage | None = None
        self._erase_image: QImage | None = None
        self._map_size: tuple[int, int] | None = None
        self._zoom = 1.0
        self._pan_offset = QPointF()
        self._fit_on_resize = True
        self._tool_mode = "add"
        self._tool_radius = 8
        self._last_stroke_point: tuple[int, int] | None = None
        self._pan_anchor: QPointF | None = None
        self._pan_start: QPointF | None = None
        self._pan_button: Qt.MouseButton | None = None
        self._space_pan_active = False

    @property
    def zoom(self) -> float:
        return self._zoom

    @property
    def pan_offset(self) -> QPointF:
        return QPointF(self._pan_offset)

    def set_map_layers(
        self,
        base_wall: np.ndarray,
        add_mask: np.ndarray,
        erase_mask: np.ndarray,
    ) -> None:
        arrays = tuple(self._as_contiguous_uint8(array) for array in (base_wall, add_mask, erase_mask))
        base, add, erase = arrays
        if base.ndim != 2 or add.ndim != 2 or erase.ndim != 2:
            raise ValueError("wall editor layers must be two-dimensional")
        if add.shape != base.shape or erase.shape != base.shape:
            raise ValueError("wall editor layers must share one shape")

        self._base_array, self._add_array, self._erase_array = arrays
        self._map_size = (base.shape[1], base.shape[0])
        self._base_image = self._grayscale_image(base)
        self._add_image = self._mask_image(add, QColor(239, 68, 68, 180))
        self._erase_image = self._mask_image(erase, QColor(34, 211, 238, 180))
        self._fit_on_resize = True
        self.fit_map()

    def clear_map_layers(self) -> None:
        self._base_array = self._add_array = self._erase_array = None
        self._base_image = self._add_image = self._erase_image = None
        self._map_size = None
        self.update()

    def refresh_layers(self) -> None:
        """Repaint masks that are shared with the editor controller in-place."""
        self.update()

    def set_tool(self, mode: str, radius: int) -> None:
        if mode not in {"add", "erase"}:
            raise ValueError(f"unknown wall editor tool: {mode}")
        if radius < 0:
            raise ValueError("wall editor brush radius must be non-negative")
        self._tool_mode = mode
        self._tool_radius = radius

    def set_zoom(self, zoom: float, *, anchor: QPointF | None = None) -> None:
        zoom = max(self._MIN_ZOOM, min(self._MAX_ZOOM, float(zoom)))
        if self._map_size is None:
            self._zoom = zoom
            self.zoom_changed.emit(self._zoom)
            return
        if anchor is None:
            anchor = QPointF(self.width() / 2.0, self.height() / 2.0)
        map_x = (anchor.x() - self._pan_offset.x()) / self._zoom
        map_y = (anchor.y() - self._pan_offset.y()) / self._zoom
        self._zoom = zoom
        self._pan_offset = QPointF(anchor.x() - map_x * zoom, anchor.y() - map_y * zoom)
        self._fit_on_resize = False
        self.zoom_changed.emit(self._zoom)
        self.update()

    def set_pan_offset(self, offset: QPointF) -> None:
        self._pan_offset = QPointF(offset)
        self._fit_on_resize = False
        self.update()

    def fit_map(self) -> None:
        if self._map_size is None or self.width() <= 0 or self.height() <= 0:
            return
        map_width, map_height = self._map_size
        usable_width = max(1, self.width() - 24)
        usable_height = max(1, self.height() - 24)
        self._zoom = max(self._MIN_ZOOM, min(self._MAX_ZOOM, min(usable_width / map_width, usable_height / map_height)))
        self._pan_offset = QPointF(
            (self.width() - map_width * self._zoom) / 2.0,
            (self.height() - map_height * self._zoom) / 2.0,
        )
        self._fit_on_resize = False
        self.zoom_changed.emit(self._zoom)
        self.update()

    def map_point_from_view(self, point: QPointF) -> tuple[int, int] | None:
        if self._map_size is None:
            return None
        map_x = int(math.floor((point.x() - self._pan_offset.x()) / self._zoom))
        map_y = int(math.floor((point.y() - self._pan_offset.y()) / self._zoom))
        width, height = self._map_size
        if not (0 <= map_x < width and 0 <= map_y < height):
            return None
        return map_x, map_y

    def paintEvent(self, _event) -> None:  # noqa: N802 - Qt method name
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor("#071019"))
        if self._base_image is None:
            painter.setPen(QColor("#91A4B8"))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "选择并加载一张已保存的地图")
            return

        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, False)
        painter.translate(self._pan_offset)
        painter.scale(self._zoom, self._zoom)
        painter.drawImage(QPointF(0, 0), self._base_image)
        painter.drawImage(QPointF(0, 0), self._add_image)
        painter.drawImage(QPointF(0, 0), self._erase_image)

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802 - Qt method name
        self.setFocus(Qt.FocusReason.MouseFocusReason)
        if self._should_start_pan(event):
            self._pan_anchor = event.position()
            self._pan_start = QPointF(self._pan_offset)
            self._pan_button = event.button()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            event.accept()
            return
        if event.button() == Qt.MouseButton.LeftButton:
            point = self.map_point_from_view(event.position())
            if point is not None:
                self._last_stroke_point = point
                self.stroke_started.emit(point)
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802 - Qt method name
        if self._pan_anchor is not None and self._pan_start is not None:
            delta = event.position() - self._pan_anchor
            self._pan_offset = self._pan_start + delta
            self._fit_on_resize = False
            self.update()
            event.accept()
            return
        if self._last_stroke_point is not None and event.buttons() & Qt.MouseButton.LeftButton:
            point = self.map_point_from_view(event.position())
            if point is not None:
                self._emit_interpolated_points(self._last_stroke_point, point)
                self._last_stroke_point = point
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # noqa: N802 - Qt method name
        if event.button() == self._pan_button and self._pan_anchor is not None:
            self._pan_anchor = self._pan_start = None
            self._pan_button = None
            self.setCursor(Qt.CursorShape.CrossCursor)
            event.accept()
            return
        if event.button() == Qt.MouseButton.LeftButton and self._last_stroke_point is not None:
            self._last_stroke_point = None
            self.stroke_finished.emit()
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def wheelEvent(self, event: QWheelEvent) -> None:  # noqa: N802 - Qt method name
        if self._map_size is None:
            event.ignore()
            return
        steps = event.angleDelta().y() / 120.0
        if steps:
            self.set_zoom(self._zoom * (1.16**steps), anchor=event.position())
        event.accept()

    def resizeEvent(self, event) -> None:  # noqa: N802 - Qt method name
        super().resizeEvent(event)
        if self._fit_on_resize and self._map_size is not None:
            self.fit_map()

    def keyPressEvent(self, event) -> None:  # noqa: N802 - Qt method name
        if event.key() == Qt.Key.Key_Space and not event.isAutoRepeat():
            self._space_pan_active = True
            if self._pan_anchor is None:
                self.setCursor(Qt.CursorShape.OpenHandCursor)
            event.accept()
            return
        super().keyPressEvent(event)

    def keyReleaseEvent(self, event) -> None:  # noqa: N802 - Qt method name
        if event.key() == Qt.Key.Key_Space and not event.isAutoRepeat():
            self._space_pan_active = False
            if self._pan_anchor is None:
                self.setCursor(Qt.CursorShape.CrossCursor)
            event.accept()
            return
        super().keyReleaseEvent(event)

    def focusOutEvent(self, event) -> None:  # noqa: N802 - Qt method name
        self._space_pan_active = False
        if self._pan_anchor is None:
            self.setCursor(Qt.CursorShape.CrossCursor)
        super().focusOutEvent(event)

    def _emit_interpolated_points(self, start: tuple[int, int], end: tuple[int, int]) -> None:
        distance = math.dist(start, end)
        spacing = max(1, self._tool_radius // 2)
        steps = max(1, math.ceil(distance / spacing))
        for index in range(1, steps + 1):
            ratio = index / steps
            point = (
                int(round(start[0] + (end[0] - start[0]) * ratio)),
                int(round(start[1] + (end[1] - start[1]) * ratio)),
            )
            self.stroke_extended.emit(point)

    def _should_start_pan(self, event: QMouseEvent) -> bool:
        if event.button() in {Qt.MouseButton.MiddleButton, Qt.MouseButton.RightButton}:
            return True
        return event.button() == Qt.MouseButton.LeftButton and (
            self._space_pan_active
            or bool(event.modifiers() & Qt.KeyboardModifier.ShiftModifier)
        )

    @staticmethod
    def _as_contiguous_uint8(array: np.ndarray) -> np.ndarray:
        return np.ascontiguousarray(np.asarray(array, dtype=np.uint8))

    @staticmethod
    def _grayscale_image(array: np.ndarray) -> QImage:
        height, width = array.shape
        return QImage(array.data, width, height, array.strides[0], QImage.Format.Format_Grayscale8)

    @staticmethod
    def _mask_image(array: np.ndarray, color: QColor) -> QImage:
        height, width = array.shape
        image = QImage(array.data, width, height, array.strides[0], QImage.Format.Format_Indexed8)
        color_table = [QColor(0, 0, 0, 0).rgba()] * 256
        color_table[255] = color.rgba()
        image.setColorTable(color_table)
        return image
