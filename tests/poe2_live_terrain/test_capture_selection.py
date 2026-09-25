from __future__ import annotations

from auto_modules.core.spatial.monitor_binding import CaptureRect, MonitorBinding
from auto_modules.ui.modes.poe2_live_terrain.capture import Poe2CaptureSelectionController


def test_poe2_selection_supports_region_and_center_modes() -> None:
    controller = Poe2CaptureSelectionController(compute_scale=lambda: (1.0, 1.0))

    region = controller.apply_region_selection(10, 20, 300, 200)
    center = controller.apply_center_selection(100, 80, 320)

    assert region.mode == "region"
    assert region.binding.rect.as_dict() == {"left": 10, "top": 20, "width": 300, "height": 200}
    assert center.mode == "center"
    assert center.binding.player_marker_position == (160, 160)
    assert center.binding.rect.as_dict() == {"left": -60, "top": -80, "width": 320, "height": 320}


def test_center_capture_size_remains_physical_pixels_on_high_dpi() -> None:
    controller = Poe2CaptureSelectionController(compute_scale=lambda: (1.5, 1.5))

    center = controller.apply_center_selection(100, 80, 320)

    assert center.binding.rect.as_dict() == {
        "left": -10,
        "top": -40,
        "width": 320,
        "height": 320,
    }
    assert center.binding.player_marker_position == (160, 160)


def test_resize_center_binding_preserves_physical_anchor_and_metadata() -> None:
    binding = MonitorBinding(
        rect=CaptureRect(2249, 107, 200, 200),
        screen_id="screen-2",
        dpi_scale_x=1.25,
        dpi_scale_y=1.5,
        player_marker_position=(100, 100),
    )

    resized = Poe2CaptureSelectionController.resize_center_binding(binding, 300)

    assert resized.rect == CaptureRect(2199, 57, 300, 300)
    assert resized.player_marker_position == (150, 150)
    assert resized.screen_id == "screen-2"
    assert resized.dpi_scale_x == 1.25
    assert resized.dpi_scale_y == 1.5
