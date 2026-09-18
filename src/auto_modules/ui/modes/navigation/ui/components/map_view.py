from __future__ import annotations

from PySide6.QtCore import QTimer, Qt, Signal
from PySide6.QtGui import QPainter
from PySide6.QtWidgets import QFrame, QGraphicsScene, QGraphicsView, QLabel, QPushButton, QVBoxLayout


class NavigationMapEmptyState(QFrame):
    """Map-local empty state that keeps the next action in the user's focus."""

    load_requested = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setProperty("role", "empty-state")
        self.title_label = QLabel("尚未加载地图")
        self.title_label.setProperty("role", "empty-title")
        self.detail_label = QLabel("选择地图后点击加载，地图会显示在这里。")
        self.detail_label.setWordWrap(True)
        self.detail_label.setProperty("role", "muted")
        self.load_button = QPushButton("加载地图")
        self.load_button.setProperty("role", "primary")
        self.load_button.clicked.connect(self.load_requested.emit)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(8)
        layout.addWidget(self.title_label)
        layout.addWidget(self.detail_label)
        layout.addWidget(self.load_button)
        self.adjustSize()

    def set_message(self, title: str, detail: str) -> None:
        self.title_label.setText(title)
        self.detail_label.setText(detail)
        self.adjustSize()

    def set_visible_for_map(self, has_map: bool) -> None:
        self.setVisible(not has_map)


class NavigationMapLegend(QFrame):
    """Small in-canvas legend for map overlay shapes and colors."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setProperty("role", "map-legend")
        label = QLabel("● 玩家   ◆ 出口   ◇ 必经点   ○ 途经点")
        label.setProperty("role", "muted")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 5, 10, 5)
        layout.addWidget(label)
        self.adjustSize()


class NavigationMapGraphicsView(QGraphicsView):
    """Graphics view with map-display zoom controls independent of map coordinates."""

    def __init__(self, scene: QGraphicsScene) -> None:
        super().__init__(scene)
        self._map_item = None
        self._empty_state = None
        self._legend = None
        self._auto_fit = True
        self._min_zoom = 0.08
        self._max_zoom = 8.0
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.AnchorViewCenter)

    def set_map_item(self, item) -> None:
        self._map_item = item
        if self._empty_state is not None:
            self._empty_state.set_visible_for_map(item is not None)
        if self._legend is not None:
            self._legend.setVisible(item is not None)
        self.fit_map()

    def set_empty_state(self, empty_state: NavigationMapEmptyState) -> None:
        self._empty_state = empty_state
        empty_state.setParent(self.viewport())
        empty_state.raise_()
        empty_state.show()
        self._position_empty_state()

    def set_legend(self, legend: NavigationMapLegend) -> None:
        self._legend = legend
        legend.setParent(self.viewport())
        legend.raise_()
        legend.hide()
        self._position_legend()

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
        QTimer.singleShot(0, self._position_empty_state)
        QTimer.singleShot(0, self._position_legend)

    def _position_empty_state(self) -> None:
        if self._empty_state is None:
            return
        self._empty_state.adjustSize()
        viewport = self.viewport()
        x = max(0, (viewport.width() - self._empty_state.width()) // 2)
        y = max(0, (viewport.height() - self._empty_state.height()) // 2)
        self._empty_state.move(x, y)

    def _position_legend(self) -> None:
        if self._legend is None:
            return
        self._legend.adjustSize()
        viewport = self.viewport()
        x = max(0, viewport.width() - self._legend.width() - 12)
        self._legend.move(x, 12)

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

    owner.empty_state = NavigationMapEmptyState(owner.view.viewport())
    owner.empty_state.load_requested.connect(owner.load_map)
    owner.view.set_empty_state(owner.empty_state)
    owner.map_legend = NavigationMapLegend(owner.view.viewport())
    owner.view.set_legend(owner.map_legend)

    owner.map_item = None
    owner.last_pos_item = None
    owner.hint_item = None
    owner.player_item = None
    owner.target_item = None
    owner.monitor_rect_item = None
    owner.game_view_rect_item = None
    owner.path_item = None
    return owner.view
