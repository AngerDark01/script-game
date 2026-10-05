from __future__ import annotations

import numpy as np

from auto_modules.core.spatial.monitor_binding import CaptureRect, MonitorBinding
from auto_modules.features.poe2.live_terrain import (
    CaptureMetadata,
    Poe2HybridProductRuntime,
    Poe2MonitorConfig,
    TerrainSnapshot,
)
from auto_modules.features.poe2.live_terrain.experimental.hybrid_localization import (
    HybridLocalizationController,
    Poe2HybridLocalizationSession,
    Poe2MemoryAnchorProvider,
    VisualLocalTracker,
)
from auto_modules.features.poe2.live_terrain.experimental.hybrid_localization.absolute_registrar import (
    AnchoredAbsoluteRegistrar,
)
from auto_modules.features.poe2.live_terrain.experimental.multiplayer_localization.composition import (
    Poe2DualLocalizationExperiment,
)
from auto_modules.ui.modes.poe2.composition import build_poe2_live_terrain_composition


class FakeScreenCapture:
    def __init__(self) -> None:
        self.calls: list[tuple[int, int, int, int]] = []

    def capture(self, left: int, top: int, width: int, height: int):
        self.calls.append((left, top, width, height))
        return np.full((height, width, 3), 17, dtype=np.uint8)


class ConfigurableRecognizer:
    def __init__(self) -> None:
        self.params = {}

    def set_params(self, params) -> None:
        self.params = dict(params)


def _bound_config(profile_id: str = "capture-test") -> Poe2MonitorConfig:
    return Poe2MonitorConfig(
        profile_id=profile_id,
        profile_name="采集测试",
        binding=MonitorBinding(CaptureRect(10, 20, 8, 6)),
        capture_size=8,
    )


def test_composition_exposes_isolated_capture_test_dependencies(tmp_path):
    capture = FakeScreenCapture()
    composition = build_poe2_live_terrain_composition(
        screen_capture=capture,
        recognizer=object(),
        writable_root=tmp_path,
    )

    assert composition.capture_test_service is not composition.service
    assert composition.capture_test_archive.root == tmp_path / "poe2_live_terrain_test"
    assert composition.capture_sample_archive.root == tmp_path / "poe2_live_terrain_test" / "samples"
    assert composition.capture_stitching_archive.root == tmp_path / "poe2_live_terrain_test" / "stitching_sessions"
    assert callable(composition.capture_stitching_session_factory)
    assert composition.capture_stitching_session_factory() is not composition.capture_stitching_session_factory()
    assert callable(composition.capture_preview)
    assert composition.capture_test_service.snapshot() is None
    assert composition.service.snapshot() is None


def test_composition_preview_uses_active_monitor_profile(tmp_path):
    capture = FakeScreenCapture()
    composition = build_poe2_live_terrain_composition(
        screen_capture=capture,
        recognizer=object(),
        writable_root=tmp_path,
    )
    config = _bound_config()
    composition.profile_store.save(config)
    composition.profile_store.activate(config.profile_id)

    frame = composition.capture_preview(config)

    assert frame.shape == (6, 8, 3)
    assert capture.calls == [(10, 20, 8, 6)]


def _snapshot() -> TerrainSnapshot:
    height, width = 40, 50
    known = np.ones((height, width), dtype=np.uint8)
    state = np.zeros((height, width), dtype=np.int8)
    state[5:-5, 6:-6] = 1
    walls = np.where(state == 0, 255, 0).astype(np.uint8)
    return TerrainSnapshot(
        metadata=CaptureMetadata(
            area_id="MapTest",
            area_hash="A1",
            instance_id="MapTest:A1",
            width=width,
            height=height,
            captured_at="2026-09-22T00:00:00+00:00",
        ),
        raw_cells=np.zeros((height, width), dtype=np.uint8),
        cell_state=state,
        known_mask=known,
        wall_layer=walls,
        explored_map=known * 255,
    )


def test_composition_factory_builds_hybrid_experiment_without_input_dependencies(tmp_path):
    composition = build_poe2_live_terrain_composition(
        screen_capture=FakeScreenCapture(),
        recognizer=object(),
        writable_root=tmp_path,
    )
    config = _bound_config()

    experiment = composition.hybrid_localization_factory(_snapshot(), lambda: config)

    assert isinstance(experiment.session, Poe2HybridLocalizationSession)
    assert isinstance(experiment.controller, HybridLocalizationController)
    assert isinstance(experiment.anchor_provider, Poe2MemoryAnchorProvider)
    assert isinstance(experiment.registrar, AnchoredAbsoluteRegistrar)
    assert experiment.registrar.config.anchor_weight == 0.65
    assert experiment.registrar.config.minimum_confidence == 0.70
    assert experiment.registrar.config.minimum_score_when_anchored == 0.35
    assert experiment.registrar.config.minimum_forward_coverage_when_anchored == 0.45
    assert experiment.registrar.config.anchor_disambiguation_gap == 1.0
    assert experiment.registrar.config.crop_radius == 150
    assert experiment.registrar.config.refine_crop_radius == 110
    assert isinstance(experiment.tracker, VisualLocalTracker)
    dependency_names = " ".join(
        type(item).__module__.lower()
        for item in (
            experiment.session,
            experiment.controller,
            experiment.anchor_provider,
            experiment.registrar,
            experiment.tracker,
        )
    )
    assert "gamepad" not in dependency_names
    assert "host" not in dependency_names
    assert "lan" not in dependency_names


def test_composition_uses_hybrid_product_runtime_for_formal_page(tmp_path):
    composition = build_poe2_live_terrain_composition(
        screen_capture=FakeScreenCapture(),
        recognizer=object(),
        writable_root=tmp_path,
    )

    assert isinstance(composition.runtime, Poe2HybridProductRuntime)
    assert composition.runtime.experiment is None


def test_formal_runtime_uses_calibrated_single_frame_registrar(tmp_path):
    composition = build_poe2_live_terrain_composition(
        screen_capture=FakeScreenCapture(),
        recognizer=object(),
        writable_root=tmp_path,
    )

    composition.runtime.configure_snapshot(_snapshot())

    registrar = composition.runtime.experiment.registrar
    assert registrar.config.minimum_confidence == 0.70
    assert registrar.config.minimum_score_when_anchored == 0.35
    assert registrar.config.anchor_weight == 0.65
    assert registrar.config.anchor_disambiguation_gap == 1.0
    assert registrar.config.coarse_angles == tuple(float(value) for value in range(0, 360, 45))
    assert registrar.config.coarse_scales[0] == 0.35
    assert registrar.config.coarse_scales[-1] == 2.45


def test_formal_runtime_selects_dual_product_experiment_from_profile(tmp_path):
    composition = build_poe2_live_terrain_composition(
        screen_capture=FakeScreenCapture(),
        recognizer=object(),
        writable_root=tmp_path,
    )

    composition.runtime.configure_monitor(Poe2MonitorConfig(tracking_mode="dual"))
    composition.runtime.configure_snapshot(_snapshot())

    assert isinstance(composition.runtime.experiment, Poe2DualLocalizationExperiment)


def test_hybrid_factory_uses_profile_first_frame_quality_gates(tmp_path):
    composition = build_poe2_live_terrain_composition(
        screen_capture=FakeScreenCapture(),
        recognizer=object(),
        writable_root=tmp_path,
    )
    config = Poe2MonitorConfig(
        first_frame_minimum_confidence=0.76,
        first_frame_anchored_score=0.42,
        first_frame_anchored_coverage=0.48,
    )

    experiment = composition.hybrid_localization_factory(_snapshot(), lambda: config)

    assert experiment.registrar.config.minimum_confidence == 0.76
    assert experiment.registrar.config.minimum_score_when_anchored == 0.42
    assert experiment.registrar.config.minimum_forward_coverage_when_anchored == 0.48


def test_hybrid_factory_applies_profile_recognition_and_boundary_matching(tmp_path):
    recognizer = ConfigurableRecognizer()
    composition = build_poe2_live_terrain_composition(
        screen_capture=FakeScreenCapture(),
        recognizer=recognizer,
        writable_root=tmp_path,
    )
    config = Poe2MonitorConfig(
        profile_id="blue-map",
        profile_name="蓝色地图",
        binding=MonitorBinding(CaptureRect(10, 20, 8, 6)),
        capture_size=8,
        recognizer_params={"edge_low": 37, "edge_high": 121},
    )

    experiment = composition.hybrid_localization_factory(_snapshot(), lambda: config)

    assert recognizer.params == {"edge_low": 37, "edge_high": 121}
    matcher = experiment.tracker.matcher
    assert matcher.max_error == 4.0
    assert matcher.min_margin == 0.02
    assert experiment.reference.wall_layer[0, 0] == 255
    assert matcher.runtime.wall_layer[0, 0] == 0
    assert matcher.runtime.wall_layer[4, 10] == 1
