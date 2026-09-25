from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from auto_modules.core.spatial.capture_geometry import CaptureShape
from auto_modules.core.spatial.monitor_binding import CaptureRect, MonitorBinding
from auto_modules.ui.modes.poe2_live_terrain.config_panel import Poe2MonitorConfigPanel
from auto_modules.ui.modes.poe2_live_terrain.capture import Poe2CaptureSelectionResult
from auto_modules.features.poe2.live_terrain.monitor_config import Poe2MonitorConfig


def test_poe2_panel_exposes_region_center_shape_and_size_controls() -> None:
    app = QApplication.instance() or QApplication([])
    panel = Poe2MonitorConfigPanel()

    assert panel.select_region_button is not None
    assert panel.select_center_button is not None
    assert panel.shape_combo.currentData() == CaptureShape.SQUARE.value
    assert panel.capture_size_spin.value() == 320
    assert panel.color_calibration_button is not None
    assert panel.advanced_visual_button is not None
    panel.deleteLater()


def test_poe2_panel_has_no_manual_orientation_controls() -> None:
    app = QApplication.instance() or QApplication([])
    panel = Poe2MonitorConfigPanel()

    assert not hasattr(panel, "map_rotation_combo")
    assert not hasattr(panel, "map_flip_horizontal_check")
    assert not hasattr(panel, "map_flip_vertical_check")
    panel.deleteLater()


def test_poe2_panel_edits_and_resets_localization_policy() -> None:
    app = QApplication.instance() or QApplication([])
    panel = Poe2MonitorConfigPanel()

    panel.first_frame_confidence_spin.setValue(0.76)
    panel.anchored_score_spin.setValue(0.42)
    panel.anchored_coverage_spin.setValue(0.48)
    panel.localization_fps_spin.setValue(25)
    panel.preview_fps_spin.setValue(10)
    config = panel.current_config()
    assert (config.first_frame_minimum_confidence, config.first_frame_anchored_score,
            config.first_frame_anchored_coverage) == (0.76, 0.42, 0.48)
    assert (config.localization_fps, config.preview_fps) == (25, 10)

    panel.reset_localization_button.click()
    assert panel.current_config().first_frame_anchored_coverage == 0.45
    assert panel.current_config().localization_fps == 30
    assert panel.current_config().preview_fps == 12
    panel.deleteLater()


def test_poe2_panel_keeps_localization_policy_after_region_selection() -> None:
    app = QApplication.instance() or QApplication([])
    panel = Poe2MonitorConfigPanel(Poe2MonitorConfig(first_frame_anchored_coverage=0.48))

    panel._apply_selection(Poe2CaptureSelectionResult(
        mode="region",
        binding=MonitorBinding(rect=CaptureRect(10, 20, 300, 300)),
        capture_size=300,
        label_text="region",
    ))

    assert panel.current_config().first_frame_anchored_coverage == 0.48
    panel.deleteLater()


def test_poe2_panel_preserves_independent_recognizer_params() -> None:
    app = QApplication.instance() or QApplication([])
    panel = Poe2MonitorConfigPanel(
        Poe2MonitorConfig(recognizer_params={"wall_hsv_min": [20, 100, 100]})
    )

    panel.set_recognizer_params({"wall_hsv_min": [21, 101, 101], "edge_low": 40})

    params = panel.current_config().recognizer_params
    assert params["wall_hsv_min"] == [21, 101, 101]
    assert params["edge_low"] == 40
    panel.deleteLater()


def test_poe2_panel_preserves_independent_stitcher_params() -> None:
    app = QApplication.instance() or QApplication([])
    panel = Poe2MonitorConfigPanel(
        Poe2MonitorConfig(stitcher_params={"canvas_size": 4200, "weight_add": 0.45})
    )

    panel.set_stitcher_params({"canvas_size": 4600, "weight_add": 0.5})

    params = panel.current_config().stitcher_params
    assert params["canvas_size"] == 4600
    assert params["weight_add"] == 0.5
    assert params["draw_quality_gate"] == 0.35
    panel.deleteLater()


def test_poe2_panel_exposes_mapping_visual_controls_and_persists_them() -> None:
    app = QApplication.instance() or QApplication([])
    panel = Poe2MonitorConfigPanel()

    panel.enable_wall_check.setChecked(False)
    panel.enable_fog_check.setChecked(False)
    panel.clahe_enabled_check.setChecked(False)
    panel.deepen_enabled_check.setChecked(False)
    panel.wall_weight_spin.setValue(61)
    panel.edge_weight_spin.setValue(39)
    panel.canny_low_spin.setValue(41)
    panel.canny_high_spin.setValue(121)
    panel.player_clear_radius_spin.setValue(34)

    params = panel.current_config().recognizer_params
    assert params["enable_wall"] is False
    assert params["enable_fog"] is False
    assert params["clahe_enabled"] is False
    assert params["deepen_enabled"] is False
    assert params["wall_weight"] == 61
    assert params["edge_weight"] == 39
    assert params["edge_low"] == 41
    assert params["edge_high"] == 121
    assert params["player_clear_radius"] == 34
    panel.deleteLater()


def test_color_calibration_requires_binding_and_respects_editable_state() -> None:
    app = QApplication.instance() or QApplication([])
    panel = Poe2MonitorConfigPanel()
    assert panel.color_calibration_button.isEnabled() is False

    panel.set_config(
        Poe2MonitorConfig(
            binding=MonitorBinding(rect=CaptureRect(10, 20, 320, 320))
        )
    )
    assert panel.color_calibration_button.isEnabled() is True

    panel.set_editable(False)
    assert panel.color_calibration_button.isEnabled() is False
    panel.set_editable(True)
    assert panel.color_calibration_button.isEnabled() is True
    panel.deleteLater()


def test_region_selection_does_not_change_center_capture_size() -> None:
    app = QApplication.instance() or QApplication([])
    panel = Poe2MonitorConfigPanel(Poe2MonitorConfig(capture_size=320))
    binding = MonitorBinding(rect=CaptureRect(10, 20, 500, 260))

    panel._apply_selection(
        Poe2CaptureSelectionResult(
            mode="region",
            binding=binding,
            capture_size=260,
            label_text="region",
        )
    )

    assert panel.current_config().capture_size == 320
    panel.deleteLater()


def test_center_capture_size_change_resizes_binding_around_same_physical_center() -> None:
    app = QApplication.instance() or QApplication([])
    binding = MonitorBinding(
        rect=CaptureRect(2249, 107, 200, 200),
        screen_id="screen-2",
        coordinate_space="physical_desktop",
        dpi_scale_x=1.25,
        dpi_scale_y=1.25,
        player_marker_position=(100, 100),
    )
    panel = Poe2MonitorConfigPanel(
        Poe2MonitorConfig(
            binding=binding,
            selection_mode="center",
            capture_size=200,
        )
    )

    panel.capture_size_spin.setValue(300)

    resized = panel.current_config().binding
    assert resized is not None
    assert resized.rect == CaptureRect(2199, 57, 300, 300)
    assert resized.player_marker_position == (150, 150)
    assert resized.screen_id == "screen-2"
    assert resized.coordinate_space == "physical_desktop"
    assert resized.dpi_scale_x == 1.25
    assert resized.dpi_scale_y == 1.25
    panel.deleteLater()


def test_region_capture_size_change_does_not_resize_binding() -> None:
    app = QApplication.instance() or QApplication([])
    binding = MonitorBinding(
        rect=CaptureRect(10, 20, 500, 260),
        player_marker_position=(250, 130),
    )
    panel = Poe2MonitorConfigPanel(
        Poe2MonitorConfig(
            binding=binding,
            selection_mode="region",
            capture_size=200,
        )
    )

    panel.capture_size_spin.setValue(300)

    assert panel.current_config().binding == binding
    panel.deleteLater()
