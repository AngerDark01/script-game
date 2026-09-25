def test_multiframe_package_exports_composition_entrypoints():
    from auto_modules.features.poe2.live_terrain.experimental.multiframe_localization import (
        build_multiframe_experiment,
        build_poe2_multiframe_experiment,
    )

    assert callable(build_multiframe_experiment)
    assert callable(build_poe2_multiframe_experiment)


def test_poe2_composition_keeps_native_coordinates_and_builds_real_evidence():
    from types import SimpleNamespace

    import numpy as np

    from auto_modules.features.poe2.live_terrain.contracts import CaptureMetadata, TerrainSnapshot
    from auto_modules.features.poe2.live_terrain.experimental.multiframe_localization import build_poe2_multiframe_experiment
    from auto_modules.features.poe2.live_terrain.player_position import PlayerPositionSample

    metadata = CaptureMetadata("Area", "hash", "Area:hash", 16, 12, "2026-09-23T00:00:00+00:00")
    snapshot = TerrainSnapshot(
        metadata,
        np.zeros((12, 16), dtype=np.uint8),
        np.ones((12, 16), dtype=np.int8),
        np.full((12, 16), 255, dtype=np.uint8),
        np.zeros((12, 16), dtype=np.uint8),
        np.full((12, 16), 255, dtype=np.uint8),
    )
    config = SimpleNamespace(
        binding=SimpleNamespace(player_marker_position=(8, 8)),
        shape="circle",
        circle_radius=7,
        map_rotation=90,
        map_flip_horizontal=True,
        map_flip_vertical=False,
    )
    recognizer = SimpleNamespace(
        preprocess_image=lambda raw: raw,
        extract_combined=lambda raw, player_pos=None: (
            np.zeros(raw.shape[:2], dtype=np.uint8),
            np.eye(raw.shape[0], raw.shape[1], dtype=np.uint8) * 255,
        ),
    )
    position_source = SimpleNamespace(
        read_once=lambda expected: PlayerPositionSample((0, 0, 0), (2.0, 3.0), "2026-09-23T00:00:00+00:00", expected)
    )
    experiment = build_poe2_multiframe_experiment(
        snapshot=snapshot,
        config_provider=lambda: config,
        preview_capture=lambda current: np.zeros((16, 16, 3), dtype=np.uint8),
        recognizer=recognizer,
        player_position_source=position_source,
        clock_ms=lambda: 1000,
    )
    experiment.session.start()
    estimate = experiment.session.tick()
    assert experiment.coordinator.anchor.position == (2.0, 3.0)
    assert estimate.status == "collecting"
    assert experiment.session._previous.raw_frame is not None
    assert experiment.session._previous.observed_mask[0, 0] == 0
    experiment.session.close()


def test_poe2_multiframe_composition_applies_profile_recognizer_params():
    from types import SimpleNamespace

    import numpy as np

    from auto_modules.features.poe2.live_terrain.contracts import CaptureMetadata, TerrainSnapshot
    from auto_modules.features.poe2.live_terrain.experimental.multiframe_localization import build_poe2_multiframe_experiment
    from auto_modules.features.poe2.live_terrain.player_position import PlayerPositionSample

    metadata = CaptureMetadata("Area", "hash", "Area:hash", 8, 8, "2026-09-23T00:00:00+00:00")
    snapshot = TerrainSnapshot(
        metadata,
        np.zeros((8, 8), dtype=np.uint8),
        np.ones((8, 8), dtype=np.int8),
        np.full((8, 8), 255, dtype=np.uint8),
        np.zeros((8, 8), dtype=np.uint8),
        np.full((8, 8), 255, dtype=np.uint8),
    )
    config = SimpleNamespace(
        binding=SimpleNamespace(player_marker_position=(4, 4)),
        shape="square",
        circle_radius=None,
        recognizer_params={"edge_low": 31},
    )
    calls = []
    recognizer = SimpleNamespace(
        set_params=lambda params: calls.append(dict(params)),
        preprocess_image=lambda raw: raw,
        extract_combined=lambda raw, player_pos=None: np.zeros(raw.shape[:2], dtype=np.uint8),
    )
    position_source = SimpleNamespace(
        read_once=lambda expected: PlayerPositionSample((0, 0, 0), (2.0, 3.0), "2026-09-23T00:00:00+00:00", expected)
    )

    experiment = build_poe2_multiframe_experiment(
        snapshot=snapshot,
        config_provider=lambda: config,
        preview_capture=lambda current: np.zeros((8, 8, 3), dtype=np.uint8),
        recognizer=recognizer,
        player_position_source=position_source,
        clock_ms=lambda: 1000,
    )

    assert calls == [{"edge_low": 31}]
    experiment.session.close()
