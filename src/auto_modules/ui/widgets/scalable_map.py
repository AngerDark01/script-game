import math

from PySide6.QtWidgets import (
    QLabel, QScrollArea, QVBoxLayout, QWidget, QSizePolicy
)
from PySide6.QtCore import QPoint, QPointF, Signal, Qt
from PySide6.QtGui import QMouseEvent, QWheelEvent, QPainter, QPen, QColor, QBrush


class _MapOverlayLabel(QLabel):
    """Lightweight marker layer that does not rebuild the map pixmap."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WA_NoSystemBackground, True)
        self._scale_factor = 1.0
        self._source_size = (0, 0)
        self._position: tuple[float, float] | None = None
        self._trajectory: tuple[tuple[float, float], ...] = ()
        self._candidates: tuple[tuple[float, float], ...] = ()

    def set_geometry(self, *, source_size, scale_factor):
        self._source_size = (int(source_size[0]), int(source_size[1]))
        self._scale_factor = float(scale_factor)
        self.update()

    def set_overlay(self, *, position=None, trajectory=(), candidates=()):
        self._position = position
        self._trajectory = tuple(trajectory or ())
        self._candidates = tuple(candidates or ())
        self.update()

    def clear_overlay(self):
        self.set_overlay()

    def _point(self, point):
        width = self._source_size[0] * self._scale_factor
        height = self._source_size[1] * self._scale_factor
        offset_x = (self.width() - width) / 2.0
        offset_y = (self.height() - height) / 2.0
        return QPointF(
            offset_x + float(point[0]) * self._scale_factor,
            offset_y + float(point[1]) * self._scale_factor,
        )

    def paintEvent(self, event):
        del event
        if not self._source_size:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        try:
            if self._candidates:
                painter.setBrush(Qt.NoBrush)
                painter.setPen(QPen(QColor(70, 170, 255, 190), max(1, int(2 * self._scale_factor)), Qt.DashLine))
                for point in self._candidates:
                    if point is not None:
                        painter.drawEllipse(self._point(point), max(7.0, 7.0 * self._scale_factor), max(7.0, 7.0 * self._scale_factor))
            if len(self._trajectory) >= 2:
                painter.setPen(QPen(QColor(255, 196, 0), max(2, int(2 * self._scale_factor))))
                for first, second in zip(self._trajectory, self._trajectory[1:]):
                    painter.drawLine(self._point(first), self._point(second))
            if self._position is not None:
                point = self._point(self._position)
                radius = max(9.0, 9.0 * self._scale_factor)
                painter.setPen(QPen(QColor(20, 230, 120), max(2, int(2 * self._scale_factor))))
                painter.setBrush(QBrush(QColor(20, 230, 120, 180)))
                painter.drawEllipse(point, radius, radius)
        finally:
            painter.end()

class ScalableMapWidget(QWidget):
    """
    可缩放的地图组件
    支持滚轮缩放、拖拽和平滑缩放
    """

    pixel_clicked = Signal(int, int)

    def __init__(self, parent=None):
        super().__init__(parent)

        self.original_pixmap = None
        self.current_pixmap = None
        self.scale_factor = 1.0
        self.min_scale = 0.1
        self.max_scale = 10.0
        # 页面可选择在首次适配视图时放大；默认保持旧页面行为。
        self.fit_scale_multiplier = 1.0

        self.is_dragging = False
        self.last_mouse_pos = None
        self._drag_total_delta = 0
        self._needs_fit_to_view = False
        self._focus_base_scale = None

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)

        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.scroll_area.setWidget(self.image_label)
        self.overlay_label = _MapOverlayLabel(self.image_label)
        self.overlay_label.setGeometry(self.image_label.rect())
        self.overlay_label.raise_()

        layout = QVBoxLayout(self)
        layout.addWidget(self.scroll_area)

        self.image_label.mousePressEvent = self._mouse_press_event
        self.image_label.mouseMoveEvent = self._mouse_move_event
        self.image_label.mouseReleaseEvent = self._mouse_release_event
        self.image_label.wheelEvent = self._wheel_event

    def set_image(self, pixmap):
        self.original_pixmap = pixmap
        self.current_pixmap = pixmap
        self.scale_factor = 1.0 # Reset scale on new image
        self._needs_fit_to_view = True
        self._focus_base_scale = None
        self.overlay_label.clear_overlay()
        if pixmap:
            self.image_label.setPixmap(pixmap)
            self.image_label.adjustSize()
            # Trigger showEvent logic if widget is already visible
            if self.isVisible():
                self.showEvent(None)
        else:
            self.image_label.clear()

    def set_overlay(self, *, position=None, trajectory=(), candidates=()):
        """Update markers without replacing or rescaling the map pixmap."""
        self.overlay_label.set_overlay(
            position=position,
            trajectory=trajectory,
            candidates=candidates,
        )

    def clear_overlay(self):
        self.overlay_label.clear_overlay()

    def showEvent(self, event):
        super().showEvent(event)
        if self._needs_fit_to_view:
            self.fit_to_view()
            self._needs_fit_to_view = False

    def fit_to_view(self):
        """自动缩放以适应窗口大小"""
        if not self.original_pixmap or self.original_pixmap.isNull():
            return

        view_size = self.scroll_area.viewport().size()
        pixmap_size = self.original_pixmap.size()

        if pixmap_size.width() == 0 or pixmap_size.height() == 0:
            return

        view_width = view_size.width() - 2
        view_height = view_size.height() - 2

        if view_width <= 0 or view_height <= 0:
            return

        scale_x = view_width / pixmap_size.width()
        scale_y = view_height / pixmap_size.height()
        
        multiplier = max(0.1, float(self.fit_scale_multiplier))
        new_scale = min(scale_x, scale_y) * multiplier
        
        self.set_scale(new_scale)

    def focus_on_point(self, point, *, zoom_multiplier: float = 1.0):
        """Zoom the source image and center the viewport on one source point.

        ``point`` is expressed in the unscaled pixmap coordinate space.  The
        method deliberately owns only presentation state; it does not alter
        the source image or any map coordinates.
        """
        if not self.original_pixmap or self.original_pixmap.isNull():
            return
        try:
            x, y = float(point[0]), float(point[1])
            multiplier = float(zoom_multiplier)
        except (TypeError, ValueError, IndexError):
            return
        if not all(math.isfinite(value) for value in (x, y, multiplier)):
            return
        if multiplier <= 0:
            raise ValueError("zoom_multiplier must be positive")
        if self._needs_fit_to_view:
            self.fit_to_view()
            self._needs_fit_to_view = False
        if self._focus_base_scale is None:
            self._focus_base_scale = self.scale_factor
        base_scale = self._focus_base_scale
        target_scale = max(self.min_scale, min(base_scale * multiplier, self.max_scale))
        if abs(target_scale - self.scale_factor) > 1e-6:
            self.set_scale(target_scale)
        viewport = self.scroll_area.viewport().size()
        scaled_x = x * self.scale_factor
        scaled_y = y * self.scale_factor
        horizontal = int(round(scaled_x - viewport.width() / 2.0))
        vertical = int(round(scaled_y - viewport.height() / 2.0))
        self.scroll_area.horizontalScrollBar().setValue(horizontal)
        self.scroll_area.verticalScrollBar().setValue(vertical)

    def zoom_in(self):
        self._focus_base_scale = None
        new_scale = self.scale_factor * 1.2
        if new_scale <= self.max_scale:
            self.set_scale(new_scale)

    def zoom_out(self):
        self._focus_base_scale = None
        new_scale = self.scale_factor / 1.2
        if new_scale >= self.min_scale:
            self.set_scale(new_scale)

    def reset_zoom(self):
        self._focus_base_scale = None
        self.set_scale(1.0)

    def set_scale(self, scale):
        self.scale_factor = max(self.min_scale, min(scale, self.max_scale))
        self._apply_scale()

    def _apply_scale(self):
        if self.original_pixmap and not self.original_pixmap.isNull():
            new_width = int(self.original_pixmap.width() * self.scale_factor)
            new_height = int(self.original_pixmap.height() * self.scale_factor)

            scaled_pixmap = self.original_pixmap.scaled(
                new_width, new_height,
                Qt.KeepAspectRatio,
                Qt.FastTransformation
            )

            self.current_pixmap = scaled_pixmap
            self.image_label.setPixmap(scaled_pixmap)
            self.image_label.adjustSize()
            self.overlay_label.setGeometry(self.image_label.rect())
            self.overlay_label.set_geometry(
                source_size=(self.original_pixmap.width(), self.original_pixmap.height()),
                scale_factor=self.scale_factor,
            )

    def _mouse_press_event(self, event):
        if event.button() == Qt.LeftButton:
            self.is_dragging = True
            self.last_mouse_pos = event.globalPosition().toPoint()
            self._drag_total_delta = 0
        elif event.button() == Qt.RightButton:
            self.reset_zoom()

    def _mouse_move_event(self, event):
        if self.is_dragging and self.last_mouse_pos:
            delta = event.globalPosition().toPoint() - self.last_mouse_pos
            self._drag_total_delta += abs(delta.x()) + abs(delta.y())
            self.scroll_area.horizontalScrollBar().setValue(
                self.scroll_area.horizontalScrollBar().value() - delta.x()
            )
            self.scroll_area.verticalScrollBar().setValue(
                self.scroll_area.verticalScrollBar().value() - delta.y()
            )
            self.last_mouse_pos = event.globalPosition().toPoint()

    def _mouse_release_event(self, event):
        if event.button() == Qt.LeftButton and self._drag_total_delta <= 3:
            self._emit_pixel_clicked(event.pos())
        self.is_dragging = False
        self.last_mouse_pos = None
        self._drag_total_delta = 0

    def _emit_pixel_clicked(self, label_pos: QPoint):
        if not self.original_pixmap or not self.current_pixmap:
            return
        if self.original_pixmap.isNull() or self.current_pixmap.isNull():
            return

        x_offset = (self.image_label.width() - self.current_pixmap.width()) // 2
        y_offset = (self.image_label.height() - self.current_pixmap.height()) // 2
        pixmap_x = label_pos.x() - x_offset
        pixmap_y = label_pos.y() - y_offset
        if pixmap_x < 0 or pixmap_y < 0:
            return
        if pixmap_x >= self.current_pixmap.width() or pixmap_y >= self.current_pixmap.height():
            return

        scale_x = self.original_pixmap.width() / self.current_pixmap.width()
        scale_y = self.original_pixmap.height() / self.current_pixmap.height()
        original_x = max(0, min(int(pixmap_x * scale_x), self.original_pixmap.width() - 1))
        original_y = max(0, min(int(pixmap_y * scale_y), self.original_pixmap.height() - 1))
        self.pixel_clicked.emit(original_x, original_y)

    def _wheel_event(self, event: QWheelEvent):
        if event.modifiers() & Qt.ControlModifier:
            if event.angleDelta().y() > 0:
                self.zoom_in()
            else:
                self.zoom_out()
        else:
            self.scroll_area.wheelEvent(event)
