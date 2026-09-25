from dataclasses import FrozenInstanceError

import pytest

from auto_modules.core.spatial.monitor_binding import (
    CaptureRect,
    MonitorBinding,
    resize_binding_around_marker,
)
from auto_modules.core.spatial import resize_binding_around_marker as public_resize_binding


def test_capture_rect_rejects_non_positive_dimensions():
    with pytest.raises(ValueError, match="positive"):
        CaptureRect(left=0, top=0, width=0, height=100)


def test_monitor_binding_is_immutable_and_serializable():
    binding = MonitorBinding(
        rect=CaptureRect(left=10, top=20, width=320, height=240),
        player_marker_position=(160, 120),
    )
    assert binding.rect.as_dict() == {"left": 10, "top": 20, "width": 320, "height": 240}
    assert binding.as_dict()["screen_id"] == "primary"
    with pytest.raises(FrozenInstanceError):
        binding.screen_id = "secondary"


def test_resize_binding_around_marker_preserves_absolute_anchor_and_metadata():
    assert public_resize_binding is resize_binding_around_marker
    binding = MonitorBinding(
        rect=CaptureRect(left=2249, top=107, width=200, height=200),
        screen_id="screen-2",
        dpi_scale_x=1.25,
        dpi_scale_y=1.5,
        player_marker_position=(100, 100),
    )

    resized = resize_binding_around_marker(binding, 300, 300)

    assert resized.rect == CaptureRect(2199, 57, 300, 300)
    assert resized.player_marker_position == (150, 150)
    assert resized.screen_id == "screen-2"
    assert resized.dpi_scale_x == 1.25
    assert resized.dpi_scale_y == 1.5
