from PySide6.QtWidgets import (
    QLabel, QScrollArea, QVBoxLayout, QWidget, QSizePolicy
)
from PySide6.QtCore import Signal, Qt
from PySide6.QtGui import QMouseEvent, QWheelEvent

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

        self.is_dragging = False
        self.last_mouse_pos = None
        self._needs_fit_to_view = False

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)

        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.scroll_area.setWidget(self.image_label)

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
        if pixmap:
            self.image_label.setPixmap(pixmap)
            self.image_label.adjustSize()
            # Trigger showEvent logic if widget is already visible
            if self.isVisible():
                self.showEvent(None)
        else:
            self.image_label.clear()

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
        
        new_scale = min(scale_x, scale_y)
        
        self.set_scale(new_scale)

    def zoom_in(self):
        new_scale = self.scale_factor * 1.2
        if new_scale <= self.max_scale:
            self.set_scale(new_scale)

    def zoom_out(self):
        new_scale = self.scale_factor / 1.2
        if new_scale >= self.min_scale:
            self.set_scale(new_scale)

    def reset_zoom(self):
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
                Qt.SmoothTransformation
            )

            self.current_pixmap = scaled_pixmap
            self.image_label.setPixmap(scaled_pixmap)
            self.image_label.adjustSize()

    def _mouse_press_event(self, event):
        if event.button() == Qt.LeftButton:
            self.is_dragging = True
            self.last_mouse_pos = event.globalPosition().toPoint()
        elif event.button() == Qt.RightButton:
            self.reset_zoom()

    def _mouse_move_event(self, event):
        if self.is_dragging and self.last_mouse_pos:
            delta = event.globalPosition().toPoint() - self.last_mouse_pos
            self.scroll_area.horizontalScrollBar().setValue(
                self.scroll_area.horizontalScrollBar().value() - delta.x()
            )
            self.scroll_area.verticalScrollBar().setValue(
                self.scroll_area.verticalScrollBar().value() - delta.y()
            )
            self.last_mouse_pos = event.globalPosition().toPoint()

    def _mouse_release_event(self, event):
        self.is_dragging = False
        self.last_mouse_pos = None

    def _wheel_event(self, event: QWheelEvent):
        if event.modifiers() & Qt.ControlModifier:
            if event.angleDelta().y() > 0:
                self.zoom_in()
            else:
                self.zoom_out()
        else:
            self.scroll_area.wheelEvent(event)
