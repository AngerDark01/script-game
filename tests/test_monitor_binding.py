from dataclasses import FrozenInstanceError

import pytest

from auto_modules.core.spatial.monitor_binding import CaptureRect, MonitorBinding


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
