from __future__ import annotations

from PySide6.QtCore import QTimer
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QMenu


class NavigationCompactUiController:
    """Own presentation-only compact/full layout switching for navigation mode."""

    def __init__(self, owner, *, route_tools_bar) -> None:
        self.owner = owner
        self.route_tools_bar = route_tools_bar
        self.compact = True
        self._build_overflow_menu()

    def _build_overflow_menu(self) -> None:
        menu = QMenu(self.owner)
        menu.setTitle("更多工具")
        entries = (
            ("路线工具", self.owner.route_tools_button),
            ("事件管理", self.owner.event_button),
            ("参数面板", self.owner.params_button),
            ("校准屏幕中心", self.owner.calibrate_button),
            ("截图窗口", self.owner.sample_window_button),
            ("保存小地图样本", self.owner.save_minimap_sample_button),
            ("地图缩小", self.owner.map_zoom_out_button),
            ("适应地图", self.owner.map_fit_button),
            ("地图放大", self.owner.map_zoom_in_button),
        )
        for label, button in entries:
            action = QAction(label, menu)
            action.triggered.connect(button.click)
            menu.addAction(action)
        self.owner.compact_more_button.setMenu(menu)

    def set_compact_mode(self, compact: bool) -> None:
        self.compact = bool(compact)
        self.owner.compact_mode_button.setText("完整布局" if self.compact else "小窗布局")
        self._set_compact_visibility()

        if self.compact:
            self.owner.view.setMinimumHeight(220)
            self.owner.view.setMaximumHeight(16777215)
            self.route_tools_bar.setVisible(self.owner.route_tools_button.isChecked())
            self._refit_map_after_layout_change()
            return

        self.owner.view.setMinimumHeight(320)
        self.owner.view.setMaximumHeight(16777215)
        self.route_tools_bar.setVisible(True)
        self._refit_map_after_layout_change()

    def _set_compact_visibility(self) -> None:
        compact = self.compact
        self.owner.compact_more_button.setVisible(compact)
        self.owner.event_button.setVisible(not compact)
        self.owner.params_button.setVisible(not compact)
        self.owner.route_tools_button.setVisible(not compact)
        for button in (
            self.owner.calibrate_button,
            self.owner.sample_window_button,
            self.owner.save_minimap_sample_button,
            self.owner.map_zoom_out_button,
            self.owner.map_fit_button,
            self.owner.map_zoom_in_button,
        ):
            button.setVisible(not compact)

    def toggle_compact_mode(self) -> None:
        self.set_compact_mode(not self.compact)

    def toggle_route_tools(self) -> None:
        if not self.compact:
            self.route_tools_bar.setVisible(True)
            return
        self.route_tools_bar.setVisible(self.owner.route_tools_button.isChecked())
        self._refit_map_after_layout_change()

    def _refit_map_after_layout_change(self) -> None:
        if hasattr(self.owner.view, "fit_map"):
            QTimer.singleShot(0, self.owner.view.fit_map)
