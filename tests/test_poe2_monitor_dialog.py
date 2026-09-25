import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication
import numpy as np

from auto_modules.ui.modes.poe2_live_terrain.monitor_dialog import Poe2MonitorConfigDialog
from auto_modules.features.poe2.live_terrain.monitor_config import Poe2MonitorConfig


def test_dialog_uses_poe2_config_and_emits_save():
    app = QApplication.instance() or QApplication([])
    dialog = Poe2MonitorConfigDialog(config=Poe2MonitorConfig())
    assert dialog.windowTitle() == "PoE2 监控配置"
    assert dialog.search_radius_spin.value() == 96
    assert dialog.config_scroll_area.widget() is dialog.panel
    received = []
    dialog.config_saved.connect(received.append)
    dialog.save()
    assert received and isinstance(received[0], Poe2MonitorConfig)
    dialog.deleteLater()


def test_color_calibration_uses_unsaved_config_and_updates_profile_params(monkeypatch):
    app = QApplication.instance() or QApplication([])
    captured = []

    class FakeColorPickerDialog:
        def __init__(self, frame, parent, recognizer_params):
            assert frame == "preview"
            assert recognizer_params["edge_low"] == 25

        def exec(self):
            return True

        def get_result(self):
            return {
                "wall_hsv": (
                    np.array([1, 2, 3]),
                    np.array([4, 5, 6]),
                ),
                "player_hsv": None,
                "recommend_sat_filter_off": True,
            }

    monkeypatch.setattr(
        "auto_modules.ui.modes.poe2_live_terrain.monitor_dialog.ColorPickerDialog",
        FakeColorPickerDialog,
    )
    dialog = Poe2MonitorConfigDialog(
        config=Poe2MonitorConfig(),
        preview_provider=lambda config: captured.append(config) or "preview",
        recognizer_params_provider=lambda: {"edge_low": 25},
    )

    dialog.open_color_calibration()

    params = dialog.current_config().recognizer_params
    assert len(captured) == 1
    assert captured[0].profile_id == dialog.current_config().profile_id
    assert captured[0].capture_size == dialog.current_config().capture_size
    assert params["wall_hsv_min"] == [1, 2, 3]
    assert params["wall_hsv_max"] == [4, 5, 6]
    assert params["sat_filter_enabled"] is False
    dialog.deleteLater()


def test_poe2_advanced_settings_keeps_and_splits_mapping_stitcher_params(monkeypatch):
    app = QApplication.instance() or QApplication([])
    captured = {}

    class Signal:
        def connect(self, callback):
            self.callback = callback

    class FakeAdvancedDialog:
        def __init__(self, parent, params):
            captured.update(params)
            self.current = dict(params)
            self.current.update({"edge_low": 44, "weight_add": 0.55})
            self.apply_params_requested = Signal()

        def use_external_apply_handler(self):
            return None

        def exec(self):
            return True

        def get_params(self):
            return self.current

    monkeypatch.setattr(
        "auto_modules.ui.modes.poe2_live_terrain.monitor_dialog.AdvancedSettingsDialog",
        FakeAdvancedDialog,
    )
    dialog = Poe2MonitorConfigDialog(
        config=Poe2MonitorConfig(
            recognizer_params={"edge_low": 25},
            stitcher_params={"weight_add": 0.45, "canvas_size": 4200},
        )
    )

    dialog.open_advanced_visual_settings()

    config = dialog.current_config()
    assert captured["edge_low"] == 25
    assert captured["weight_add"] == 0.45
    assert config.recognizer_params["edge_low"] == 44
    assert "weight_add" not in config.recognizer_params
    assert config.stitcher_params["weight_add"] == 0.55
    assert config.stitcher_params["canvas_size"] == 4200
    dialog.deleteLater()
