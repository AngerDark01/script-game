"""Independent PoE2 monitor profile editor."""

from __future__ import annotations

from typing import Any, Callable

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QMessageBox,
    QScrollArea,
    QVBoxLayout,
)

from auto_modules.core.mapping import MapStitcher
from auto_modules.core.vision import HSVRecognizer
from auto_modules.features.poe2.live_terrain import (
    Poe2MonitorConfig,
    Poe2MonitorConfigStore,
    Poe2MonitorProfileStore,
)
from auto_modules.ui.dialogs.advanced_settings_dialog import AdvancedSettingsDialog
from auto_modules.ui.dialogs.color_picker_dialog import ColorPickerDialog

from .config_panel import Poe2MonitorConfigPanel


class Poe2MonitorConfigDialog(QDialog):
    """PoE2-only dialog using the mapping interaction as a reference."""

    config_saved = Signal(object)

    def __init__(
        self,
        *,
        config: Poe2MonitorConfig | None = None,
        config_store: Poe2MonitorConfigStore | None = None,
        profile_store: Poe2MonitorProfileStore | None = None,
        preview_provider: Callable[[Poe2MonitorConfig], Any] | None = None,
        recognizer_params_provider: Callable[[], dict[str, Any]] | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("PoE2 监控配置")
        self.resize(560, 760)
        self.config_store = config_store
        self.profile_store = profile_store
        self.preview_provider = preview_provider
        self.recognizer_params_provider = recognizer_params_provider
        if config is None and profile_store is not None:
            config = profile_store.active()
        self.config = config or (config_store.load() if config_store is not None else Poe2MonitorConfig())
        self._build_ui()
        self.panel.set_config(self.config)
        self.panel.set_recognizer_params(
            self._complete_recognizer_params(),
            emit=False,
        )

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.addWidget(QLabel("PoE2 小地图监控区域与定位参数"))
        self.panel = Poe2MonitorConfigPanel(self.config, parent=self)
        self.panel.config_changed.connect(self._on_panel_changed)
        self.panel.color_calibration_requested.connect(self.open_color_calibration)
        self.panel.advanced_visual_requested.connect(self.open_advanced_visual_settings)
        self.config_scroll_area = QScrollArea(self)
        self.config_scroll_area.setWidgetResizable(True)
        self.config_scroll_area.setWidget(self.panel)
        root.addWidget(self.config_scroll_area, 1)

        self.buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        self.buttons.accepted.connect(self.save)
        self.buttons.rejected.connect(self.reject)
        root.addWidget(self.buttons)

        # Preserve the old dialog's public widget names for existing callers.
        self.search_radius_spin = self.panel.search_radius_spin
        self.match_threshold_spin = self.panel.match_threshold_spin
        self.sample_interval_spin = self.panel.sample_interval_spin
        self.shape_combo = self.panel.shape_combo
        self.capture_size_spin = self.panel.capture_size_spin
        self.circle_radius_spin = self.panel.circle_radius_spin
        self.binding_label = self.panel.binding_label
        self.color_calibration_button = self.panel.color_calibration_button
        self.advanced_visual_button = self.panel.advanced_visual_button

    def _on_panel_changed(self, config: Poe2MonitorConfig) -> None:
        self.config = config

    def current_config(self) -> Poe2MonitorConfig:
        return self.panel.current_config()

    def set_config(self, config: Poe2MonitorConfig) -> None:
        self.config = config
        self.panel.set_config(config)
        self.panel.set_recognizer_params(
            self._complete_recognizer_params(),
            emit=False,
        )

    def _complete_recognizer_params(self) -> dict:
        defaults = HSVRecognizer().get_params()
        if callable(self.recognizer_params_provider):
            provided = self.recognizer_params_provider()
            if provided:
                defaults.update(dict(provided))
        defaults.update(self.panel.stored_recognizer_params())
        return defaults

    def _complete_stitcher_params(self) -> dict:
        defaults = MapStitcher.default_params(canvas_size=5000, draw_scale=2.0)
        defaults.update(self.panel.stored_stitcher_params())
        return defaults

    def open_color_calibration(self) -> None:
        if not callable(self.preview_provider):
            QMessageBox.warning(self, "颜色校准", "当前运行时不支持校准截图")
            return
        try:
            frame = self.preview_provider(self.panel.current_config())
        except Exception as exc:
            QMessageBox.warning(self, "颜色校准", str(exc))
            return
        params = self._complete_recognizer_params()
        dialog = ColorPickerDialog(
            frame,
            self,
            recognizer_params=params,
        )
        if not dialog.exec():
            return
        result = dialog.get_result()
        wall_hsv = result.get("wall_hsv")
        if wall_hsv:
            params["wall_hsv_min"] = wall_hsv[0].tolist()
            params["wall_hsv_max"] = wall_hsv[1].tolist()
        player_hsv = result.get("player_hsv")
        if player_hsv:
            params["player_hsv_min"] = player_hsv[0].tolist()
            params["player_hsv_max"] = player_hsv[1].tolist()
        if result.get("recommend_sat_filter_off"):
            params["sat_filter_enabled"] = False
        self.panel.set_recognizer_params(params)

    def open_advanced_visual_settings(self) -> None:
        recognizer_params = self._complete_recognizer_params()
        stitcher_params = self._complete_stitcher_params()
        recognizer_keys = set(HSVRecognizer().get_params())
        stitcher_keys = set(MapStitcher.default_params())
        pending_recognizer = dict(recognizer_params)
        pending_stitcher = dict(stitcher_params)
        params = {**recognizer_params, **stitcher_params}
        dialog = AdvancedSettingsDialog(self, params)
        dialog.use_external_apply_handler()

        def remember(changes: dict) -> None:
            pending_recognizer.update(
                {key: value for key, value in changes.items() if key in recognizer_keys}
            )
            pending_stitcher.update(
                {key: value for key, value in changes.items() if key in stitcher_keys}
            )

        dialog.apply_params_requested.connect(remember)
        if dialog.exec():
            remember(dialog.get_params())
            self.panel.set_recognizer_params(pending_recognizer, emit=False)
            self.panel.set_stitcher_params(pending_stitcher)

    def save(self) -> None:
        self.config = self.current_config()
        if self.profile_store is not None:
            self.profile_store.save(self.config)
            self.profile_store.activate(self.config.profile_id)
        elif self.config_store is not None:
            self.config_store.save(self.config)
        self.config_saved.emit(self.config)
        self.accept()

    def set_editable(self, enabled: bool) -> None:
        self.panel.set_editable(enabled)
        self.buttons.button(QDialogButtonBox.Save).setEnabled(bool(enabled))


__all__ = ["Poe2MonitorConfigDialog"]
