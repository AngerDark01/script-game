from __future__ import annotations

import pytest

from auto_modules.core.spatial.capture_geometry import CaptureShape
from auto_modules.core.spatial.monitor_binding import CaptureRect, MonitorBinding
from auto_modules.features.poe2.live_terrain.monitor_config import Poe2MonitorConfig


def test_monitor_config_round_trips_circle_shape_and_profile_name() -> None:
    config = Poe2MonitorConfig(
        profile_id="single",
        profile_name="单人圆形",
        shape=CaptureShape.CIRCLE,
        capture_size=320,
        circle_radius=140.0,
    )

    restored = Poe2MonitorConfig.from_dict(config.as_dict())

    assert restored == config


def test_monitor_config_defaults_keep_legacy_payload_compatible() -> None:
    config = Poe2MonitorConfig.from_dict({"search_radius": 80})

    assert config.profile_id == "default"
    assert config.profile_name == "默认配置"
    assert config.shape is CaptureShape.SQUARE
    assert config.search_radius == 80
    assert config.stitcher_params["canvas_size"] == 5000
    assert config.stitcher_params["draw_scale"] == 2.0
    assert config.stitcher_params["draw_quality_gate"] == 0.35
    assert config.first_frame_minimum_confidence == 0.70
    assert config.first_frame_anchored_score == 0.35
    assert config.first_frame_anchored_coverage == 0.45
    assert config.localization_fps == 30
    assert config.preview_fps == 12


def test_monitor_config_round_trips_localization_policy() -> None:
    config = Poe2MonitorConfig(
        first_frame_minimum_confidence=0.76,
        first_frame_anchored_score=0.42,
        first_frame_anchored_coverage=0.48,
        localization_fps=25,
        preview_fps=10,
    )

    assert Poe2MonitorConfig.from_dict(config.as_dict()) == config


@pytest.mark.parametrize("values", [
    {"first_frame_minimum_confidence": 1.1},
    {"first_frame_anchored_score": -0.1},
    {"first_frame_anchored_coverage": 0.0},
    {"localization_fps": 0},
    {"localization_fps": 61},
    {"preview_fps": 31},
    {"localization_fps": 10, "preview_fps": 12},
])
def test_monitor_config_rejects_invalid_localization_policy(values: dict) -> None:
    with pytest.raises(ValueError):
        Poe2MonitorConfig(**values)


def test_monitor_config_round_trips_independent_recognizer_params() -> None:
    config = Poe2MonitorConfig(
        recognizer_params={
            "wall_hsv_min": [20, 100, 100],
            "wall_hsv_max": [40, 255, 255],
            "transparent_mode": False,
            "edge_low": 35,
        }
    )

    payload = config.as_dict()
    restored = Poe2MonitorConfig.from_dict(payload)

    assert restored.recognizer_params == config.recognizer_params
    payload["recognizer_params"]["wall_hsv_min"][0] = 99
    assert config.recognizer_params["wall_hsv_min"][0] == 20


def test_monitor_config_round_trips_and_detaches_stitcher_params() -> None:
    config = Poe2MonitorConfig(
        stitcher_params={
            "canvas_size": 4200,
            "draw_scale": 1.5,
            "weight_add": 0.45,
        }
    )

    payload = config.as_dict()
    restored = Poe2MonitorConfig.from_dict(payload)

    assert restored.stitcher_params["canvas_size"] == 4200
    assert restored.stitcher_params["draw_scale"] == 1.5
    assert restored.stitcher_params["weight_add"] == 0.45
    assert restored.stitcher_params["draw_quality_gate"] == 0.35
    payload["stitcher_params"]["weight_add"] = 9.0
    assert config.stitcher_params["weight_add"] == 0.45


def test_legacy_manual_orientation_is_ignored_and_not_reserialized() -> None:
    config = Poe2MonitorConfig.from_dict(
        {
            "map_rotation": 90,
            "map_flip_horizontal": True,
            "map_flip_vertical": True,
        }
    )

    assert not hasattr(config, "map_rotation")
    assert "map_rotation" not in config.as_dict()
    assert "map_flip_horizontal" not in config.as_dict()
    assert "map_flip_vertical" not in config.as_dict()


def test_center_config_normalizes_legacy_binding_to_capture_size() -> None:
    config = Poe2MonitorConfig(
        binding=MonitorBinding(
            rect=CaptureRect(2249, 107, 200, 200),
            player_marker_position=(100, 100),
        ),
        selection_mode="center",
        capture_size=300,
    )

    assert config.binding is not None
    assert config.binding.rect == CaptureRect(2199, 57, 300, 300)
    assert config.binding.player_marker_position == (150, 150)


def test_region_config_does_not_normalize_binding_to_capture_size() -> None:
    binding = MonitorBinding(rect=CaptureRect(10, 20, 500, 260))

    config = Poe2MonitorConfig(
        binding=binding,
        selection_mode="region",
        capture_size=300,
    )

    assert config.binding == binding
