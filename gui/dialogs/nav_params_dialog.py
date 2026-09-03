"""
导航参数对话框模块。

本文件现在只作为参数面板 shell：窗口生命周期、信号、NavConfig 更新和屏幕半径估算留在这里；
具体 tab/section/widget 创建放在 `gui.dialogs.nav_params` 子模块。
"""

from __future__ import annotations

from PySide6.QtCore import QSignalBlocker, Signal
from PySide6.QtWidgets import QApplication, QDialog, QTabWidget, QVBoxLayout, QWidget

from gui.dialogs.nav_params.config_binding import (
    connect_config_bindings,
    parse_config_text_value,
    replace_config_value,
    write_config_to_widgets,
)
from gui.dialogs.nav_params.layout_helpers import apply_nav_params_window_mode
from gui.dialogs.nav_params.screen_estimator import estimate_click_radii
from gui.dialogs.nav_params.sections import build_action_bar, build_navigation_parameter_tabs
from gui.navigation_params import NavConfig


class NavParametersDialog(QDialog):
    """Non-modal navigation parameter editor backed by `NavConfig`."""

    parameters_changed = Signal(NavConfig)
    save_requested = Signal()
    save_default_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("导航参数面板")
        self.setModal(False)

        self.config: NavConfig | None = None
        self._action_buttons_connected = False
        self._signals_connected = False
        self._compact_mode = True
        self.setSizeGripEnabled(True)

        self._init_ui()
        self._connect_signals()
        self.set_compact_mode(True, resize_window=False)
        self.resize(520, 640)

    def _init_ui(self) -> None:
        """Build the dialog shell and delegate section creation."""
        dialog_layout = QVBoxLayout(self)
        self.nav_tabs = QTabWidget()
        dialog_layout.addWidget(self.nav_tabs, 1)
        build_navigation_parameter_tabs(self, self.nav_tabs)
        dialog_layout.addLayout(build_action_bar(self))

    def set_compact_mode(self, compact: bool, *, resize_window: bool = True) -> None:
        """Switch only the parameter dialog window sizing policy."""
        self._compact_mode = bool(compact)
        apply_nav_params_window_mode(self, self._compact_mode, resize_window=resize_window)

    def _toggle_compact_mode(self) -> None:
        self.set_compact_mode(not self._compact_mode)

    def _connect_signals(self) -> None:
        """Wire config-bound widgets and footer buttons once."""
        if self._signals_connected:
            return

        connect_config_bindings(
            self,
            self._update_config_value,
            self._update_config_text_value,
        )

        if not self._action_buttons_connected:
            self.nav_save_btn.clicked.connect(self.save_requested)
            self.nav_save_default_btn.clicked.connect(self.save_default_requested)
            self.nav_compact_mode_btn.clicked.connect(self._toggle_compact_mode)
            self.nav_auto_click_radius_btn.clicked.connect(self._auto_estimate_click_radius)
            self._action_buttons_connected = True
        self._signals_connected = True

    def _update_config_value(
        self,
        sub_config_name: str | None,
        attr_name: str,
        value,
        to_bool: bool = False,
    ) -> None:
        """Update one numeric/boolean config field and emit the full config snapshot."""
        if self.config is None:
            return

        if to_bool:
            value = bool(value)

        self.config = replace_config_value(
            self.config,
            sub_config_name,
            attr_name,
            value,
        )

        self.parameters_changed.emit(self.config)
        self.nav_status_label.setText("有未保存的修改")

    def _update_config_text_value(self, sub_config_name: str | None, attr_name: str, text: str) -> None:
        """Update one literal text config field when the text is parseable."""
        if self.config is None:
            return

        parsed, value = parse_config_text_value(text)
        if not parsed:
            return

        self._update_config_value(sub_config_name, attr_name, value)

    def _screen_physical_bounds_for_center(self, center):
        """Find physical screen bounds containing a calibrated physical center."""
        if not center:
            return None

        cx, cy = int(center[0]), int(center[1])
        screens = QApplication.screens() or [QApplication.primaryScreen()]
        fallback = None
        for screen in screens:
            if screen is None:
                continue
            dpr = screen.devicePixelRatio() or 1.0
            geometry = screen.geometry()
            left = int(round(geometry.x() * dpr))
            top = int(round(geometry.y() * dpr))
            right = left + int(round(geometry.width() * dpr))
            bottom = top + int(round(geometry.height() * dpr))
            bounds = (left, top, right, bottom)
            fallback = fallback or bounds
            if left <= cx <= right and top <= cy <= bottom:
                return bounds
        return fallback

    def _auto_estimate_click_radius(self) -> None:
        """Estimate click radii from calibrated center and physical screen size."""
        if self.config is None:
            return
        if not self.config.game_screen_center:
            self.nav_status_label.setText("请先校准屏幕中心")
            return

        bounds = self._screen_physical_bounds_for_center(self.config.game_screen_center)
        if not bounds:
            self.nav_status_label.setText("无法读取屏幕尺寸")
            return

        estimate = estimate_click_radii(self.config.game_screen_center, bounds)
        if estimate is None:
            self.nav_status_label.setText("屏幕中心不在当前屏幕范围内")
            return

        self.nav_movement_min_click_radius_spin.setValue(estimate.min_radius)
        self.nav_movement_max_click_radius_spin.setValue(estimate.max_radius)
        self.nav_status_label.setText(
            f"已估算点击半径: {estimate.min_radius}-{estimate.max_radius}px"
        )

    def set_config_to_ui(self, config: NavConfig) -> None:
        """Write a `NavConfig` snapshot into the panel without emitting widget changes."""
        self.config = config
        signal_blockers = [QSignalBlocker(w) for w in self.findChildren(QWidget)]
        write_config_to_widgets(self, config)
        self.nav_status_label.setText("参数已加载")
        self._connect_signals()
        del signal_blockers
