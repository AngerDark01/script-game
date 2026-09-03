from __future__ import annotations

from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QPainter
from PySide6.QtWidgets import QGraphicsScene, QGraphicsView


class NavigationMapGraphicsView(QGraphicsView):
    """Graphics view with map-display zoom controls independent of map coordinates."""

    def __init__(self, scene: QGraphicsScene) -> None:
        super().__init__(scene)
        self._map_item = None
        self._auto_fit = True
        self._min_zoom = 0.08
        self._max_zoom = 8.0
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.AnchorViewCenter)

    def set_map_item(self, item) -> None:
        self._map_item = item
        self.fit_map()

    def fit_map(self) -> None:
        if self._map_item is None:
            return
        self._auto_fit = True
        self.resetTransform()
        self.fitInView(self._map_item, Qt.KeepAspectRatio)

    def zoom_in(self) -> None:
        self._zoom_by(1.2)

    def zoom_out(self) -> None:
        self._zoom_by(1 / 1.2)

    def reset_map_zoom(self) -> None:
        if self._map_item is None:
            self.resetTransform()
            return
        self._auto_fit = False
        self.resetTransform()
        self.centerOn(self._map_item)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if self._auto_fit and self._map_item is not None:
            QTimer.singleShot(0, self.fit_map)

    def wheelEvent(self, event) -> None:
        if event.modifiers() & Qt.ControlModifier:
            if event.angleDelta().y() > 0:
                self.zoom_in()
            else:
                self.zoom_out()
            event.accept()
            return
        super().wheelEvent(event)

    def _zoom_by(self, factor: float) -> None:
        current = max(abs(float(self.transform().m11())), abs(float(self.transform().m22())))
        next_zoom = current * float(factor)
        if next_zoom < self._min_zoom or next_zoom > self._max_zoom:
            return
        self._auto_fit = False
        self.scale(float(factor), float(factor))


def build_navigation_map_view(owner) -> QGraphicsView:
    """Create the navigation scene/view and initialize scene item references."""
    owner.scene = QGraphicsScene()
    owner.scene.installEventFilter(owner)
    owner.view = NavigationMapGraphicsView(owner.scene)
    owner.view.setRenderHint(QPainter.Antialiasing)
    owner.view.setDragMode(QGraphicsView.ScrollHandDrag)

    owner.map_item = None
    owner.last_pos_item = None
    owner.hint_item = None
    owner.player_item = None
    owner.target_item = None
    owner.monitor_rect_item = None
    owner.game_view_rect_item = None
    owner.path_item = None
    return owner.view
