from __future__ import annotations

import os
import time
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import numpy as np
import pytest
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QApplication

from auto_modules.core.mapping import MapStitcher
from auto_modules.features.poe2.live_terrain.capture_samples import CaptureSampleArchive
from auto_modules.features.poe2.live_terrain.contracts import (
    CaptureMetadata,
    TerrainSessionState,
    TerrainSnapshot,
)
from auto_modules.features.poe2.live_terrain.experimental.hybrid_localization.models import (
    HybridLocalizationMode,
    HybridLocalizationState,
    SimilarityTransform2D,
)
from auto_modules.features.poe2.live_terrain.experimental.multiplayer_follow import (
    ControlMode,
    FollowObservation,
    FollowState,
    PositionSample,
    RoleId,
)
from auto_modules.features.poe2.live_terrain.experimental.multiplayer_localization import (
    DualFirstFrameResult,
    DualMotionState,
    PlayerLocalization,
    Poe2EntityPositionSample,
)
from auto_modules.features.poe2.live_terrain.player_position import PlayerPositionSample
from auto_modules.features.poe2.live_terrain.stitching_archive import (
    Poe2StitchingArchive,
)
from auto_modules.features.poe2.live_terrain.stitching_session import (
    Poe2StitchingSession,
)
from auto_modules.ui.modes.poe2_live_terrain.capture_test_page import (
    Poe2CaptureTestPage,
)
import auto_modules.ui.modes.poe2_live_terrain.capture_test_page as capture_test_page_module
import auto_modules.ui.modes.poe2_live_terrain.probe_mixin as probe_mixin_module
from auto_modules.ui.modes.poe2_live_terrain.presenter import (
    localization_display_point,
    localization_source_point,
)


def _snapshot() -> TerrainSnapshot:
    metadata = CaptureMetadata("Area", "hash", "Area:hash", 2, 2, "2026-09-21T00:00:00+00:00")
    return TerrainSnapshot(
        metadata,
        np.zeros((2, 2), dtype=np.uint8),
        np.ones((2, 2), dtype=np.int8),
        np.full((2, 2), 255, dtype=np.uint8),
        np.zeros((2, 2), dtype=np.uint8),
        np.full((2, 2), 255, dtype=np.uint8),
    )


class FakeService:
    def __init__(self) -> None:
        self.state = TerrainSessionState.NEW
        self.snapshot_value = _snapshot()
        self.error: Exception | None = None

    def initialize(self) -> None:
        if self.error is not None:
            raise self.error
        self.state = TerrainSessionState.READY_TO_CAPTURE

    def capture(self) -> TerrainSnapshot:
        if self.error is not None:
            raise self.error
        self.state = TerrainSessionState.CAPTURED
        return self.snapshot_value

    def reset(self) -> None:
        self.state = TerrainSessionState.NEW

    def snapshot(self):
        return self.snapshot_value if self.state is TerrainSessionState.CAPTURED else None


class FakeArchive:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.calls: list[TerrainSnapshot] = []

    def save(self, snapshot: TerrainSnapshot) -> Path:
        self.calls.append(snapshot)
        return self.root / "latest.npz"


class FakeRecognizer:
    def __init__(self):
        self.combined_options = []

    def preprocess_image(self, frame):
        return frame + 1

    def extract_combined(self, frame, player_pos=None, **options):
        self.combined_options.append(dict(options))
        mask = np.full(frame.shape[:2], 255, dtype=np.uint8)
        return mask, mask, np.zeros_like(mask)


class FakePlayerPositionSource:
    def __init__(self, error: Exception | None = None) -> None:
        self.error = error
        self.instances: list[str] = []

    def read_once(self, expected_instance_id: str):
        self.instances.append(expected_instance_id)
        if self.error is not None:
            raise self.error
        return PlayerPositionSample.from_world(
            world=(250.0 / 23.0, 250.0 / 23.0, -12.0),
            captured_at="2026-09-22T03:27:56+00:00",
            area_instance=expected_instance_id,
        )


def _hybrid_state(position=(1.0, 1.0)):
    return HybridLocalizationState(
        mode=HybridLocalizationMode.LOCAL_TRACKING,
        position=position,
        latest_confirmed_position=position,
        trajectory=(position,),
        registration=None,
        source="anchored_absolute",
        confidence=0.9,
        reason="",
        recovery_revision=1,
    )


class FakeHybridSession:
    def __init__(self):
        self.starts = 0
        self.stops = 0
        self.retries = 0
        self.ticks = 0
        self.listeners = []

    def add_listener(self, listener):
        self.listeners.append(listener)

    def start(self):
        self.starts += 1

    def stop(self):
        self.stops += 1

    def retry_recovery(self):
        self.retries += 1

    def tick(self):
        self.ticks += 1
        value = _hybrid_state()
        for listener in self.listeners:
            listener(value)
        return value


class FakeHybridFactory:
    def __init__(self):
        self.calls = []
        self.session = FakeHybridSession()

    def __call__(self, snapshot, config_provider):
        self.calls.append((snapshot, config_provider))
        return SimpleNamespace(
            session=self.session,
            anchor_provider=SimpleNamespace(read_count=1),
        )


def _app():
    return QApplication.instance() or QApplication([])


def test_capture_test_page_lifecycle_and_explicit_save(tmp_path):
    _app()
    service = FakeService()
    archive = FakeArchive(tmp_path)
    page = Poe2CaptureTestPage(
        service,
        archive=archive,
        monitor_config=SimpleNamespace(sample_interval_ms=100, binding=None),
        preview_provider=lambda _config: np.zeros((8, 8, 3), dtype=np.uint8),
        recognizer=FakeRecognizer(),
    )

    assert page.capture_button.isEnabled() is False
    assert page.save_button.isEnabled() is False
    page.initialize_session()
    assert page.capture_button.isEnabled() is True
    page.capture_map()
    assert page.save_button.isEnabled() is True
    page.save_map()

    assert archive.calls == [service.snapshot_value]
    assert "latest.npz" in page.archive_label.text()
    page.reset_session()
    assert page.map_widget.original_pixmap is None
    assert page.save_button.isEnabled() is False


def test_preview_failure_clears_previous_frame_and_reports_current_error(tmp_path):
    _app()
    calls = []

    def provider(_config):
        if calls:
            raise RuntimeError("capture unavailable")
        calls.append(True)
        return np.zeros((8, 8, 3), dtype=np.uint8)

    page = Poe2CaptureTestPage(
        FakeService(),
        archive=FakeArchive(tmp_path),
        monitor_config=SimpleNamespace(sample_interval_ms=100, binding=None),
        preview_provider=provider,
        recognizer=FakeRecognizer(),
    )
    page.refresh_preview()
    assert not page.frame_preview.pixmap().isNull()
    page.refresh_preview()

    assert page.frame_preview.pixmap().isNull()
    assert page.feature_preview.pixmap().isNull()
    assert "capture unavailable" in page.error_label.text()


def test_reset_stops_preview_timer(tmp_path):
    _app()
    page = Poe2CaptureTestPage(
        FakeService(),
        archive=FakeArchive(tmp_path),
        monitor_config=SimpleNamespace(sample_interval_ms=10, binding=None),
        preview_provider=lambda _config: np.zeros((8, 8, 3), dtype=np.uint8),
    )
    page.start_preview()
    assert page.preview_timer.isActive()
    page.reset_session()
    assert not page.preview_timer.isActive()


def test_capture_failure_clears_previous_map_and_save_action(tmp_path):
    _app()
    service = FakeService()
    page = Poe2CaptureTestPage(
        service,
        archive=FakeArchive(tmp_path),
        monitor_config=SimpleNamespace(sample_interval_ms=100, binding=None),
        preview_provider=None,
    )
    page.initialize_session()
    page.capture_map()
    assert page.save_button.isEnabled()

    service.error = RuntimeError("game process changed")
    service.state = TerrainSessionState.READY_TO_CAPTURE
    page.capture_map()

    assert page.map_widget.original_pixmap is None
    assert not page.save_button.isEnabled()
    assert "game process changed" in page.error_label.text()


def test_capture_reads_player_position_and_marks_map(tmp_path):
    _app()
    source = FakePlayerPositionSource()
    page = Poe2CaptureTestPage(
        FakeService(),
        archive=FakeArchive(tmp_path),
        monitor_config=SimpleNamespace(sample_interval_ms=100, binding=None),
        preview_provider=None,
        player_position_source=source,
    )

    page.initialize_session()
    page.capture_map()

    assert source.instances == ["Area:hash"]
    assert "人物网格位置：1.00，1.00" in page.metadata_label.text()
    assert page.player_position_label.text() == "人物位置：网格 (1.00, 1.00)"
    assert page.error_label.text() == ""


def test_position_failure_keeps_captured_map_and_reports_error(tmp_path):
    _app()
    page = Poe2CaptureTestPage(
        FakeService(),
        archive=FakeArchive(tmp_path),
        monitor_config=SimpleNamespace(sample_interval_ms=100, binding=None),
        preview_provider=None,
        player_position_source=FakePlayerPositionSource(RuntimeError("position unavailable")),
    )

    page.initialize_session()
    page.capture_map()

    assert page.map_widget.original_pixmap is not None
    assert page.save_button.isEnabled()
    assert page.player_position_label.text() == "人物位置：读取失败"
    assert "地图仍已获取" in page.error_label.text()
    assert "position unavailable" in page.error_label.text()


def test_capture_monitor_button_reuses_one_window_and_shutdown_closes_it(tmp_path):
    _app()
    page = Poe2CaptureTestPage(
        FakeService(),
        archive=FakeArchive(tmp_path),
        sample_archive=CaptureSampleArchive(tmp_path / "samples"),
        stitching_session_factory=lambda: Poe2StitchingSession(
            stitcher_factory=lambda: MapStitcher(canvas_size=100, draw_scale=1.0)
        ),
        stitching_archive=Poe2StitchingArchive(tmp_path / "stitching"),
        monitor_config=SimpleNamespace(
            sample_interval_ms=100,
            binding=SimpleNamespace(player_marker_position=(4, 4)),
            as_dict=lambda: {"profile_id": "test"},
        ),
        preview_provider=lambda _config: np.zeros((8, 8, 3), dtype=np.uint8),
        recognizer=FakeRecognizer(),
    )

    page.open_capture_monitor()
    first = page.capture_monitor_window
    assert first is not None
    assert first.preview_timer.isActive()
    page.open_capture_monitor()

    assert page.capture_monitor_window is first
    page.shutdown()

    assert not first.preview_timer.isActive()
    assert not first.isVisible()


def test_capture_test_page_close_detaches_logger_handler(tmp_path):
    _app()
    page = Poe2CaptureTestPage(
        FakeService(),
        archive=FakeArchive(tmp_path),
        monitor_config=SimpleNamespace(sample_interval_ms=100, binding=None),
        preview_provider=None,
    )
    handler = page._log_handler
    logger = page._logger

    assert handler in logger.handlers
    page.close()

    assert handler not in logger.handlers


def test_capture_test_page_suspend_releases_follow_outputs(tmp_path):
    _app()
    page, outputs, _transform = _dual_target_page(tmp_path)
    page.start_dual_target_experiment()
    page._on_follow_map_click(20, 20)

    page.suspend()

    assert page._dual_target_runtime is None
    assert not page._dual_target_timer.isActive()
    assert all(output.calls[-1] == "stop" for output in outputs.values())


def test_capture_test_page_shutdown_releases_follow_outputs(tmp_path):
    page, outputs, _transform = _dual_target_page(tmp_path)
    page.start_dual_target_experiment()
    page._on_follow_map_click(20, 20)

    page.shutdown()

    assert page._dual_target_runtime is None
    assert not page._dual_target_timer.isActive()
    assert all(output.calls[-1] == "stop" for output in outputs.values())


def test_hybrid_controls_require_map_and_drive_one_session(tmp_path):
    _app()
    service = FakeService()
    factory = FakeHybridFactory()
    page = Poe2CaptureTestPage(
        service,
        archive=FakeArchive(tmp_path),
        monitor_config=SimpleNamespace(sample_interval_ms=100, binding=None),
        preview_provider=lambda _config: np.zeros((8, 8, 3), dtype=np.uint8),
        hybrid_localization_factory=factory,
    )

    assert not page.start_hybrid_button.isEnabled()
    page.initialize_session()
    page.capture_map()
    assert page.start_hybrid_button.isEnabled()

    page.start_hybrid_localization()
    assert page.hybrid_timer.isActive()
    assert factory.session.starts == 1
    assert factory.session.ticks == 1
    assert "anchored_absolute" in page.hybrid_status_label.text()
    assert "1.00, 1.00" in page.hybrid_position_label.text()

    page.retry_hybrid_recovery()
    assert factory.session.retries == 1
    page.stop_hybrid_localization()
    assert not page.hybrid_timer.isActive()
    assert factory.session.stops == 1


def test_hybrid_failure_details_are_visible_in_status(tmp_path):
    _app()
    page = Poe2CaptureTestPage(
        FakeService(),
        archive=FakeArchive(tmp_path),
        monitor_config=SimpleNamespace(sample_interval_ms=100, binding=None),
        preview_provider=lambda _config: np.zeros((8, 8, 3), dtype=np.uint8),
    )
    page._hybrid_experiment = SimpleNamespace(
        anchor_provider=SimpleNamespace(read_count=1),
    )
    state = HybridLocalizationState(
        mode=HybridLocalizationMode.RECOVERY_REQUIRED,
        position=None,
        latest_confirmed_position=None,
        trajectory=(),
        registration=None,
        source="failed",
        confidence=0.0,
        reason="absolute_registration_failed",
        recovery_revision=1,
        diagnostics={
            "reason": "best candidate score is below the anchored threshold",
            "best_score": 0.244,
            "best_forward_coverage": 1.0,
            "best_angle": 327.0,
            "best_scale": 0.29,
            "best_anchor_error": 41.91,
        },
    )

    page.handle_hybrid_state(state)

    text = page.hybrid_status_label.text()
    assert "候选分 0.244" in text
    assert "覆盖 1.000" in text
    assert "角度 327.0°" in text
    assert "比例 0.290" in text
    assert "锚点误差 41.91" in text
    assert "best candidate score is below the anchored threshold" in text


def test_dual_first_frame_button_requires_a_captured_map(tmp_path):
    _app()
    recognizer = FakeRecognizer()
    page = Poe2CaptureTestPage(
        FakeService(),
        archive=FakeArchive(tmp_path),
        monitor_config=SimpleNamespace(sample_interval_ms=100, binding=None),
        preview_provider=lambda _config: np.zeros((20, 20, 3), dtype=np.uint8),
        recognizer=recognizer,
    )

    assert page.dual_first_frame_button.text() == "双人首帧实验"
    assert not page.dual_first_frame_button.isEnabled()
    page.run_dual_first_frame_experiment()

    assert "请先获取当前地图" in page.error_label.text()


def test_localization_interval_honors_configured_fps_instead_of_legacy_sample_cap(tmp_path):
    _app()
    page = Poe2CaptureTestPage(
        FakeService(),
        archive=FakeArchive(tmp_path),
        monitor_config=SimpleNamespace(
            sample_interval_ms=100,
            localization_fps=30,
            preview_fps=12,
            binding=None,
        ),
        preview_provider=None,
        recognizer=None,
    )

    assert page._localization_interval() == 33
    assert page._preview_interval() == 100


def test_dual_first_frame_experiment_renders_two_players_without_timer(tmp_path):
    _app()
    recognizer = FakeRecognizer()
    capture_calls = []

    class _DualSource:
        def read_many(self, expected_instance_id):
            return (
                Poe2EntityPositionSample(
                    "p1", "Metadata/Characters/A", (11.5, 11.5, 0.0),
                    (1.0, 1.0), "2026-09-22T03:27:56+00:00", expected_instance_id, 1,
                ),
                Poe2EntityPositionSample(
                    "p2", "Metadata/Characters/B", (12.5, 12.5, 0.0),
                    (1.5, 1.5), "2026-09-22T03:27:56+00:00", expected_instance_id, 2,
                ),
            )

    class _DualExperiment:
        def __init__(self, provider):
            self.provider = provider

        def read_anchors(self, instance_id):
            return self.provider.read_once(instance_id)

        def register(self, frame, *, reference, anchors, observation):
            players = {
                "p1": PlayerLocalization(
                    "p1", "observation-0", (5.0, 5.0), (1.0, 1.0), (1.0, 1.0), 0.5, 0.90, True,
                ),
                "p2": PlayerLocalization(
                    "p2", "observation-1", (15.0, 15.0), (1.5, 1.5), (1.5, 1.5), 0.6, 0.88, True,
                ),
            }
            return DualFirstFrameResult(
                "accepted", "one transform explains both player markers and memory anchors",
                SimpleNamespace(
                    transform=SimpleNamespace(
                        angle_degrees=90.0,
                        reflect_horizontal=True,
                        scale=1.0,
                    )
                ),
                players,
                {"candidate_count": 2, "evaluated_assignment_count": 1},
            )

    page = Poe2CaptureTestPage(
        FakeService(),
        archive=FakeArchive(tmp_path),
        monitor_config=SimpleNamespace(sample_interval_ms=100, binding=None),
        preview_provider=lambda _config: (capture_calls.append(True) or np.zeros((20, 20, 3), dtype=np.uint8)),
        recognizer=recognizer,
        dual_player_position_source=_DualSource(),
        dual_first_frame_factory=lambda provider: _DualExperiment(provider),
    )
    page.initialize_session()
    page.capture_map()
    capture_calls.clear()
    page.dual_first_frame_button.click()

    assert page.dual_first_frame_button.isEnabled()
    assert len(capture_calls) == 1
    assert "双人首帧：accepted" in page.dual_first_frame_status_label.text()
    assert "p1" in page.dual_first_frame_status_label.text()
    assert "p2" in page.dual_first_frame_status_label.text()
    assert "方向 90.0°，水平镜像" in page.dual_first_frame_status_label.text()
    assert page.map_widget.original_pixmap is not None
    assert not page.hybrid_timer.isActive()
    page.refresh_preview()
    assert recognizer.combined_options[-1] == {
        "exclude_player": False,
        "exclude_dynamic": False,
    }
    page.capture_map()
    page.refresh_preview()
    assert recognizer.combined_options[-1] == {}


def test_dual_motion_start_reads_once_then_visual_ticks_do_not_read_memory(tmp_path):
    _app()
    reads = []

    class _Source:
        def read_many(self, expected_instance_id):
            reads.append(expected_instance_id)
            return (
                Poe2EntityPositionSample(
                    "p1", "Metadata/Characters/A", (11.5, 11.5, 0.0),
                    (1.0, 1.0), "2026-09-22T03:27:56+00:00", expected_instance_id, 1,
                ),
                Poe2EntityPositionSample(
                    "p2", "Metadata/Characters/B", (12.5, 12.5, 0.0),
                    (1.5, 1.5), "2026-09-22T03:27:56+00:00", expected_instance_id, 2,
                ),
            )

    transform = SimilarityTransform2D(0, False, 1.0, (0.0, 0.0))
    players = {
        identity: PlayerLocalization(
            identity, identity, point, point, point, 0.0, 0.9, True,
        )
        for identity, point in {"p1": (5.0, 5.0), "p2": (15.0, 15.0)}.items()
    }

    class _Experiment:
        def __init__(self, provider):
            self.provider = provider

        def read_anchors(self, instance_id):
            return self.provider.read_once(instance_id)

        def register(self, *args, **kwargs):
            return DualFirstFrameResult(
                "accepted", "ok", SimpleNamespace(transform=transform), players,
            )

    state = DualMotionState("tracking", "visual", {"p1": (1.0, 1.0), "p2": (1.5, 1.5)}, transform)

    class _Tracker:
        recover = False

        def start(self, frame, result, initial_candidates):
            return state

        def tick(self, frame, candidates):
            if self.recover:
                return DualMotionState(
                    "recovery_required", "wall_failed", {"p1": None, "p2": None},
                    transform, recovery_requested=True, recovery_revision=1,
                )
            return state

    tracker = _Tracker()
    page = Poe2CaptureTestPage(
        FakeService(), archive=FakeArchive(tmp_path),
        monitor_config=SimpleNamespace(sample_interval_ms=100, binding=None),
        preview_provider=lambda _config: np.zeros((20, 20, 3), dtype=np.uint8),
        recognizer=FakeRecognizer(), dual_player_position_source=_Source(),
        dual_first_frame_factory=lambda provider: _Experiment(provider),
        dual_motion_tracker_factory=lambda reference: tracker,
    )
    page.initialize_session()
    page.capture_map()
    page.start_dual_motion_button.click()
    assert page._dual_motion_timer.isActive()
    assert reads == ["Area:hash"]
    page._tick_dual_motion()
    page._tick_dual_motion()
    assert reads == ["Area:hash"]
    assert "p1" in page.dual_motion_status_label.text()
    assert "p2" in page.dual_motion_status_label.text()
    page.stop_dual_motion_button.click()
    assert not page._dual_motion_timer.isActive()

    # A recovery start must force a new memory-anchor/visual registration
    # instead of reusing the accepted first frame.
    page._program_probe_recovery_target = (12.0, 12.0)
    page._program_probe_recovery_identity = "p1"
    page._program_probe_recovery_controller = 1
    page._program_probe_recovery_attempts = 1
    page._start_dual_motion(recovery=True)
    assert len(reads) == 2
    page.stop_dual_motion()

    page.start_dual_motion_button.click()
    assert len(reads) == 3
    page._dual_last_recovery_at_ms = int(time.time() * 1000)
    tracker.recover = True
    page._tick_dual_motion()
    assert not page._dual_motion_timer.isActive()
    assert len(reads) == 3
    assert "手动重启" in page.dual_motion_status_label.text()


def test_initialize_stops_existing_dual_and_follow_timers(tmp_path):
    _app()
    page = Poe2CaptureTestPage(
        FakeService(), archive=FakeArchive(tmp_path),
        monitor_config=SimpleNamespace(sample_interval_ms=100, binding=None),
        preview_provider=None,
    )
    page._dual_motion_timer.start()
    page._follow_timer.start()

    page.initialize_session()

    assert not page._dual_motion_timer.isActive()
    assert not page._follow_timer.isActive()
    assert page._latest_dual_state is None


def test_follow_requires_explicit_role_assignment_not_dictionary_order(tmp_path):
    _app()
    page = Poe2CaptureTestPage(
        FakeService(), archive=FakeArchive(tmp_path),
        monitor_config=SimpleNamespace(sample_interval_ms=100, binding=None),
        preview_provider=None,
    )
    page.initialize_session()
    page.capture_map()
    transform = SimilarityTransform2D(0, False, 1.0, (0.0, 0.0))
    page._dual_map_transform = transform
    page._dual_follow_reference = SimpleNamespace(wall_layer=np.zeros((32, 32), dtype=np.uint8))
    page._latest_dual_state = DualMotionState(
        "tracking", "visual", {"role-b": (15.0, 15.0), "role-a": (5.0, 5.0)}, transform,
    )

    page.start_follow_experiment()
    assert page._follow_runtime is None
    page._sync_follow_role_choices(page._latest_dual_state.players)
    page.follow_p1_combo.setCurrentIndex(page.follow_p1_combo.findData("role-a"))
    page.follow_p2_combo.setCurrentIndex(page.follow_p2_combo.findData("role-a"))
    page.start_follow_experiment()
    assert page._follow_runtime is None
    page.follow_p2_combo.setCurrentIndex(page.follow_p2_combo.findData("role-b"))
    page.follow_mode_combo.setCurrentIndex(page.follow_mode_combo.findData("p1_manual"))
    page.start_follow_experiment()

    assert page._follow_runtime is not None
    assert page._follow_runtime.contact_required_samples == 4
    assert page._follow_runtime.mode_for(RoleId("local-device", "role-a")) is ControlMode.MANUAL
    assert page._follow_runtime.mode_for(RoleId("local-device", "role-b")) is ControlMode.SIMULATED
    page.stop_follow_experiment()
    page.capture_map()
    assert page.follow_p1_combo.currentData() is None
    assert page.follow_p2_combo.currentData() is None


def test_invalid_follow_start_does_not_arm_target_probe(tmp_path):
    page, _outputs, _transform = _dual_target_page(tmp_path)
    page._latest_dual_state = None

    page.start_follow_experiment()

    assert page._experiment_composition.follow_probe.armed is False


def test_dual_frame_redraw_does_not_advance_follow_simulation_twice(tmp_path):
    _app()
    page = Poe2CaptureTestPage(
        FakeService(), archive=FakeArchive(tmp_path),
        monitor_config=SimpleNamespace(sample_interval_ms=100, binding=None),
        preview_provider=None,
    )
    transform = SimilarityTransform2D(0, False, 1.0, (0.0, 0.0))
    state = DualMotionState("tracking", "visual", {"role-a": (5.0, 5.0)}, transform)
    page._follow_runtime = object()
    ticks = []
    page._tick_follow_experiment = lambda: ticks.append(True)

    page._render_dual_motion_state(state, (32, 32))

    assert ticks == []


def test_dual_motion_follow_overlay_is_painted_once_per_frame(tmp_path):
    page, _outputs, transform = _dual_target_page(tmp_path)
    page.follow_p1_combo.setCurrentIndex(page.follow_p1_combo.findData("role-a"))
    page.follow_p2_combo.setCurrentIndex(page.follow_p2_combo.findData("role-b"))
    page.follow_mode_combo.setCurrentIndex(page.follow_mode_combo.findData("p1_leads"))
    state = DualMotionState(
        "tracking", "visual", {"role-a": (25.0, 8.0), "role-b": (5.0, 8.0)}, transform,
    )
    page._latest_dual_state = state
    page._latest_dual_captured_at_ms = int(time.time() * 1000)
    page.start_follow_experiment()
    calls = []
    page.map_widget.set_overlay = lambda **kwargs: calls.append(kwargs)

    page._render_dual_motion_state(state, (32, 32))

    assert len(calls) == 1


def test_program_probe_relocalization_resumes_saved_target_on_fresh_dual_frame(tmp_path):
    _app()
    page = Poe2CaptureTestPage(
        FakeService(), archive=FakeArchive(tmp_path),
        monitor_config=SimpleNamespace(sample_interval_ms=100, binding=None),
        preview_provider=None,
    )
    transform = SimilarityTransform2D(0, False, 1.0, (0.0, 0.0))
    page._latest_dual_state = DualMotionState(
        "tracking", "visual", {"role-a": (7.0, 8.0)}, transform,
    )
    page._latest_dual_captured_at_ms = int(time.time() * 1000)
    page._sync_follow_role_choices(page._latest_dual_state.players)
    page._program_probe_recovery_target = (24.0, 25.0)
    page._program_probe_recovery_identity = "role-a"
    page._program_probe_recovery_controller = 1
    page._program_probe_recovery_attempts = 2
    resumed = []
    page._start_program_move_probe_at = lambda point, **kwargs: resumed.append((point, kwargs))

    page._maybe_resume_program_probe_after_relocalization()

    assert resumed == [((24.0, 25.0), {"_confirmed": True})]
    assert page._program_probe_recovery_target is None
    assert page.program_probe_role_combo.currentData() == "role-a"
    assert page.program_probe_controller_combo.currentData() == 1


def test_program_probe_relocalization_accepts_wall_trusted_degraded_frame(tmp_path):
    _app()
    page = Poe2CaptureTestPage(
        FakeService(), archive=FakeArchive(tmp_path),
        monitor_config=SimpleNamespace(sample_interval_ms=100, binding=None),
        preview_provider=None,
    )
    transform = SimilarityTransform2D(0, False, 1.0, (0.0, 0.0))
    now = int(time.time() * 1000)
    page._latest_dual_state = DualMotionState(
        "degraded", "markers_partial_grace", {"role-a": (7.0, 8.0)}, transform,
        wall_quality=1.0,
        diagnostics={"wall_trusted": True},
    )
    page._latest_dual_captured_at_ms = now
    page._sync_follow_role_choices(page._latest_dual_state.players)
    page._program_probe_recovery_target = (24.0, 25.0)
    page._program_probe_recovery_identity = "role-a"
    page._program_probe_recovery_controller = 1
    resumed = []
    page._start_program_move_probe_at = lambda point, **kwargs: resumed.append((point, kwargs))

    page._maybe_resume_program_probe_after_relocalization()

    assert resumed == [((24.0, 25.0), {"_confirmed": True})]


def test_program_probe_has_no_total_map_duration_limit(tmp_path, monkeypatch):
    """A long map run stays active; only explicit operational boundaries stop it."""
    _app()
    page = Poe2CaptureTestPage(
        FakeService(), archive=FakeArchive(tmp_path),
        monitor_config=SimpleNamespace(sample_interval_ms=100, binding=None),
        preview_provider=None,
    )
    role = RoleId("local-device", "role-a")
    now_ms = int(time.time() * 1000)

    class _Output:
        def __init__(self):
            self.applied = 0

        def apply(self, _observation, *, elapsed_ms):
            self.applied += 1

        def release_all(self):
            raise AssertionError("a long route must not be stopped by elapsed time")

    observation = SimpleNamespace(
        position=(1.0, 1.0), target_position=(20.0, 20.0), vector=(1.0, 0.0),
        route=(), diagnostics={}, distance=20.0, reason="moving",
        state=SimpleNamespace(value="following"),
    )

    class _Runtime:
        map_identity = SimpleNamespace(map_id="Area", map_version="hash")

        def update_follower_position(self, _sample):
            return None

        def refresh_simulated_target(self, *, now_ms):
            return None

        def tick(self, *, now_ms):
            return {role.key: observation}

    output = _Output()
    page._program_probe_output = output
    page._program_probe_runtime = _Runtime()
    page._program_probe_role = role
    page._program_probe_game_pid = 123
    page._program_probe_started_at_ms = now_ms - 24 * 60 * 60 * 1000
    # A legacy/injected duration value must not reintroduce a map-run ceiling.
    page._program_probe_max_duration_ms = 1
    page._program_probe_ticks = 1
    page._latest_dual_state = SimpleNamespace(
        players={"role-a": (1.0, 1.0)}, recovery_requested=False,
    )
    page._latest_dual_captured_at_ms = now_ms
    page._native_route_vector_for_input = lambda vector: vector
    page._update_program_probe_local_contact = lambda *_args, **_kwargs: None
    page._render_program_probe_overlay = lambda *_args, **_kwargs: None
    monkeypatch.setattr(probe_mixin_module, "is_process_foreground", lambda _pid: True)

    page._tick_program_move_probe()

    assert output.applied == 1
    assert page._program_probe_output is output


def test_follow_waits_for_first_click_and_keeps_real_players_visible(tmp_path):
    _app()
    page = Poe2CaptureTestPage(
        FakeService(), archive=FakeArchive(tmp_path),
        monitor_config=SimpleNamespace(sample_interval_ms=100, binding=None),
        preview_provider=None,
    )
    page.initialize_session()
    page.capture_map()
    page.map_widget.set_image(QPixmap(32, 32))
    transform = SimilarityTransform2D(0, False, 1.0, (0.0, 0.0))
    state = DualMotionState(
        'tracking', 'visual', {'role-a': (5.0, 5.0), 'role-b': (8.0, 8.0)}, transform,
    )
    page._dual_motion_tracker = object()
    page._dual_map_source_size = (32, 32)
    page._dual_map_transform = transform
    page._dual_follow_reference = SimpleNamespace(wall_layer=np.zeros((32, 32), dtype=np.uint8))
    page._render_dual_motion_state(state, (32, 32))
    page.follow_p1_combo.setCurrentIndex(page.follow_p1_combo.findData('role-a'))
    page.follow_p2_combo.setCurrentIndex(page.follow_p2_combo.findData('role-b'))

    page.start_follow_experiment()
    assert page._follow_runtime is not None
    assert page._follow_runtime.remote.position is None
    assert not page._follow_timer.isActive()
    assert '等待点击' in page.follow_status_label.text()

    page._on_follow_map_click(20, 20)
    assert page._follow_timer.isActive()
    assert page._follow_runtime.remote.position.position == (20.0, 20.0)
    assert dict(page.map_widget.overlay_label._players) == state.players

    now_ms = int(time.time() * 1000) + 100
    page._last_follow_observations = page._follow_runtime.tick(now_ms=now_ms)
    page._render_follow_overlay()
    assert dict(page.map_widget.overlay_label._players) == state.players
    assert page.map_widget.overlay_label._candidates
    rendered_routes = page.map_widget.overlay_label._routes
    assert rendered_routes
    assert rendered_routes[0][1][0] == page._last_follow_observations["local-device:role-a"].position
    assert rendered_routes[0][1][-1] == (20.0, 20.0)

    page._on_follow_map_click(24, 20)
    page._on_follow_map_click(22, 21)
    assert page._follow_runtime.remote.position.position == (22.0, 21.0)
    assert page.map_widget.overlay_label._target == (22.0, 21.0)
    assert dict(page.map_widget.overlay_label._players) == state.players
    page.stop_follow_experiment()
    assert page.map_widget.overlay_label._target is None
    assert not page.map_widget.overlay_label._routes
    assert page.map_widget.overlay_label._position == (5.0, 5.0)
    assert page.map_widget.overlay_label._candidates == ((8.0, 8.0),)


def test_map_click_is_displayed_and_logged_before_follow_starts(tmp_path):
    _app()
    page = Poe2CaptureTestPage(
        FakeService(), archive=FakeArchive(tmp_path),
        monitor_config=SimpleNamespace(sample_interval_ms=100, binding=None),
        preview_provider=None,
    )
    page.initialize_session()
    page.capture_map()
    page.map_widget.set_image(QPixmap(32, 32))
    transform = SimilarityTransform2D(17.0, True, 1.25, (2.0, -1.0))
    state = DualMotionState(
        'tracking', 'visual', {'role-a': (5.0, 5.0)}, transform,
    )
    page._latest_dual_state = state
    page._dual_map_source_size = (32, 32)
    page._dual_map_transform = transform
    page._dual_follow_reference = SimpleNamespace(wall_layer=np.zeros((32, 32), dtype=np.uint8))

    page._on_follow_map_click(12, 13)

    assert page._follow_runtime is None
    assert page._clicked_target_source == (12.0, 13.0)
    assert page._clicked_target_native is not None
    assert page._clicked_target_display is not None
    assert page.map_widget.overlay_label._target == page._clicked_target_display
    log_text = page.session_log.toPlainText()
    assert "step=map_click.received" in log_text
    assert "step=map_click.transformed" in log_text
    assert "step=map_click.accepted" in log_text


def test_dual_motion_reuses_an_already_accepted_first_frame(tmp_path):
    _app()
    page = Poe2CaptureTestPage(
        FakeService(), archive=FakeArchive(tmp_path),
        monitor_config=SimpleNamespace(sample_interval_ms=100, binding=None),
        preview_provider=None,
    )
    page.initialize_session()
    page.capture_map()
    transform = SimilarityTransform2D(0, False, 1.0, (0.0, 0.0))
    result = DualFirstFrameResult(
        "accepted", "ok", SimpleNamespace(transform=transform),
        {
            "p1": PlayerLocalization("p1", "c1", (5.0, 5.0), (5.0, 5.0), (5.0, 5.0), 0.0, 0.9, True),
            "p2": PlayerLocalization("p2", "c2", (8.0, 8.0), (8.0, 8.0), (8.0, 8.0), 0.0, 0.9, True),
        },
    )
    page._last_dual_first_frame_result = result
    page._dual_initial_frame = SimpleNamespace(
        wall_mask=np.zeros((20, 20), dtype=np.uint8),
        local_player=(10.0, 10.0),
    )
    page._dual_initial_candidates = ()
    page._latest_dual_captured_at_ms = int(time.time() * 1000)
    page.run_dual_first_frame_experiment = lambda **_kwargs: (_ for _ in ()).throw(
        AssertionError("restarting realtime must not recapture an accepted first frame")
    )
    page._snapshot = _snapshot()
    page._dual_follow_reference = SimpleNamespace(wall_layer=np.zeros((20, 20), dtype=np.uint8))
    page._render_dual_motion_state = lambda *_args: None
    page.dual_motion_tracker_factory = lambda _reference: SimpleNamespace(
        start=lambda frame, accepted, candidates: DualMotionState(
            "tracking", "first_frame", {"p1": (5.0, 5.0), "p2": (8.0, 8.0)}, transform,
        ),
    )
    page._start_dual_motion(recovery=False)

    assert page._dual_motion_tracker is not None
    assert page._latest_dual_captured_at_ms is None
    page.stop_dual_motion()


def test_dual_motion_recovery_consumes_accepted_async_first_frame(tmp_path):
    """An accepted background recovery result must restart realtime tracking."""
    _app()
    page = Poe2CaptureTestPage(
        FakeService(), archive=FakeArchive(tmp_path),
        monitor_config=SimpleNamespace(sample_interval_ms=100, binding=None),
        preview_provider=None,
    )
    page.initialize_session()
    page.capture_map()
    transform = SimilarityTransform2D(0, False, 1.0, (0.0, 0.0))
    result = DualFirstFrameResult(
        "accepted", "ok", SimpleNamespace(transform=transform),
        {
            "p1": PlayerLocalization("p1", "c1", (5.0, 5.0), (5.0, 5.0), (5.0, 5.0), 0.0, 0.9, True),
            "p2": PlayerLocalization("p2", "c2", (8.0, 8.0), (8.0, 8.0), (8.0, 8.0), 0.0, 0.9, True),
        },
    )
    page._last_dual_first_frame_result = result
    page._dual_initial_frame = SimpleNamespace(
        wall_mask=np.zeros((20, 20), dtype=np.uint8),
        local_player=(10.0, 10.0),
    )
    page._dual_initial_candidates = ()
    page._dual_follow_reference = SimpleNamespace(wall_layer=np.zeros((20, 20), dtype=np.uint8))
    page._render_dual_motion_state = lambda *_args: None
    page.dual_motion_tracker_factory = lambda _reference: SimpleNamespace(
        start=lambda frame, accepted, candidates: DualMotionState(
            "tracking", "relocalized", {"p1": (5.0, 5.0), "p2": (8.0, 8.0)}, transform,
        ),
    )

    # This is the exact hand-off used by _on_dual_first_frame_worker_result
    # after a background recovery worker returns status=accepted.
    page._start_dual_motion(recovery=True, first_frame_ready=True)

    assert page._dual_motion_tracker is not None
    assert page._dual_motion_timer.isActive()
    assert "首帧配准未通过" not in page.dual_motion_status_label.text()
    page.stop_dual_motion()


def test_dual_motion_start_failure_keeps_accepted_first_frame_for_retry(tmp_path):
    _app()
    page = Poe2CaptureTestPage(
        FakeService(), archive=FakeArchive(tmp_path),
        monitor_config=SimpleNamespace(sample_interval_ms=100, binding=None),
        preview_provider=None,
    )
    page.initialize_session()
    page.capture_map()
    transform = SimilarityTransform2D(0, False, 1.0, (0.0, 0.0))
    result = DualFirstFrameResult(
        "accepted", "ok", SimpleNamespace(transform=transform),
        {
            "p1": PlayerLocalization("p1", "c1", (5.0, 5.0), (5.0, 5.0), (5.0, 5.0), 0.0, 0.9, True),
            "p2": PlayerLocalization("p2", "c2", (8.0, 8.0), (8.0, 8.0), (8.0, 8.0), 0.0, 0.9, True),
        },
    )
    page._last_dual_first_frame_result = result
    page._dual_initial_frame = SimpleNamespace(wall_mask=np.zeros((20, 20), dtype=np.uint8), local_player=(10.0, 10.0))
    page._dual_initial_candidates = ()
    page._dual_follow_reference = SimpleNamespace(wall_layer=np.zeros((20, 20), dtype=np.uint8))
    page.dual_motion_tracker_factory = lambda _reference: (_ for _ in ()).throw(RuntimeError("tracker failed"))
    page._start_dual_motion(recovery=False)
    assert page._last_dual_first_frame_result is result
    assert page._dual_initial_frame is not None
    assert "启动失败" in page.dual_motion_status_label.text()


def test_dual_motion_clone_failure_falls_back_without_sharing_gui_recognizer(tmp_path):
    _app()
    page = Poe2CaptureTestPage(
        FakeService(),
        archive=FakeArchive(tmp_path),
        monitor_config=SimpleNamespace(
            sample_interval_ms=100,
            localization_fps=30,
            binding=None,
            dual_marker_profiles=(),
        ),
        preview_provider=lambda _config: np.zeros((20, 20, 3), dtype=np.uint8),
        recognizer=FakeRecognizer(),
    )
    page.initialize_session()
    page.capture_map()
    transform = SimilarityTransform2D(0, False, 1.0, (0.0, 0.0))
    result = DualFirstFrameResult(
        "accepted", "ok", SimpleNamespace(transform=transform),
        {
            "p1": PlayerLocalization("p1", "c1", (5.0, 5.0), (5.0, 5.0), (5.0, 5.0), 0.0, 0.9, True),
            "p2": PlayerLocalization("p2", "c2", (8.0, 8.0), (8.0, 8.0), (8.0, 8.0), 0.0, 0.9, True),
        },
    )
    page._last_dual_first_frame_result = result
    page._dual_initial_frame = SimpleNamespace(
        wall_mask=np.zeros((20, 20), dtype=np.uint8),
        local_player=(10.0, 10.0),
    )
    page._dual_initial_candidates = ()
    page._snapshot = _snapshot()
    page._dual_follow_reference = SimpleNamespace(wall_layer=np.zeros((20, 20), dtype=np.uint8))
    page._render_dual_motion_state = lambda *_args: None
    page.dual_motion_tracker_factory = lambda _reference: SimpleNamespace(
        start=lambda frame, accepted, candidates: DualMotionState(
            "tracking", "first_frame", {"p1": (5.0, 5.0), "p2": (8.0, 8.0)}, transform,
        ),
    )

    page._start_dual_motion(recovery=False)

    assert page._dual_motion_worker is None
    assert page._dual_motion_timer.isActive()
    assert page._dual_motion_timer.interval() == page._localization_interval()
    page.stop_dual_motion()


def test_dual_motion_restart_waits_for_retired_worker_finished(tmp_path):
    _app()
    page = Poe2CaptureTestPage(
        FakeService(),
        archive=FakeArchive(tmp_path),
        monitor_config=SimpleNamespace(sample_interval_ms=100, binding=None),
        preview_provider=None,
    )
    calls = []
    page._snapshot = _snapshot()
    retired = SimpleNamespace(generation=42, is_running=lambda: False)
    page._retired_dual_motion_workers = [retired]
    page._dual_motion_restart_pending = True
    page._start_dual_motion = lambda **kwargs: calls.append(kwargs)

    page._on_dual_worker_finished(42)
    QApplication.processEvents()

    assert calls[0]["recovery"] is True
    assert isinstance(calls[0]["preserve_follow"], bool)
    assert page._dual_motion_restart_pending is None


def test_dual_motion_restart_checks_all_retired_worker_states(tmp_path):
    _app()
    page = Poe2CaptureTestPage(
        FakeService(), archive=FakeArchive(tmp_path),
        monitor_config=SimpleNamespace(sample_interval_ms=100, binding=None),
        preview_provider=None,
    )
    page._snapshot = _snapshot()
    calls = []
    page._retired_dual_motion_workers = [
        SimpleNamespace(generation=42, is_running=lambda: False),
        SimpleNamespace(generation=43, is_running=lambda: False),
    ]
    page._dual_motion_restart_pending = True
    page._start_dual_motion = lambda **kwargs: calls.append(kwargs)

    page._on_dual_worker_finished(42)
    QApplication.processEvents()

    assert calls[0]["recovery"] is True
    assert isinstance(calls[0]["preserve_follow"], bool)


def test_dual_motion_does_not_read_first_frame_while_retired_worker_is_running(tmp_path):
    _app()
    page = Poe2CaptureTestPage(
        FakeService(), archive=FakeArchive(tmp_path),
        monitor_config=SimpleNamespace(sample_interval_ms=100, binding=None),
        preview_provider=None,
    )
    page._snapshot = _snapshot()
    page._retired_dual_motion_workers = [SimpleNamespace(generation=41, is_running=True)]
    page.run_dual_first_frame_experiment = lambda **_kwargs: (_ for _ in ()).throw(
        AssertionError("must not read a new first frame while the retired worker is running")
    )

    page._start_dual_motion(recovery=False)

    assert page._dual_motion_restart_pending is False
    assert "等待旧截图线程退出" in page.dual_motion_status_label.text()


def test_dual_motion_finished_does_not_restart_after_page_close(tmp_path):
    _app()
    page = Poe2CaptureTestPage(
        FakeService(), archive=FakeArchive(tmp_path),
        monitor_config=SimpleNamespace(sample_interval_ms=100, binding=None),
        preview_provider=None,
    )
    calls = []
    page._closing = True
    page._dual_motion_restart_pending = True
    page._retired_dual_motion_workers = [SimpleNamespace(generation=42, is_running=False)]
    page._start_dual_motion = lambda **kwargs: calls.append(kwargs)

    page._on_dual_worker_finished(42)
    QApplication.processEvents()

    assert calls == []
    assert page._dual_motion_restart_pending is None


def test_stopping_dual_motion_cancels_deferred_restart(tmp_path):
    _app()
    page = Poe2CaptureTestPage(
        FakeService(), archive=FakeArchive(tmp_path),
        monitor_config=SimpleNamespace(sample_interval_ms=100, binding=None),
        preview_provider=None,
    )
    page._dual_motion_restart_pending = True
    page._latest_dual_captured_at_ms = int(time.time() * 1000)

    page.stop_dual_motion()

    assert page._dual_motion_restart_pending is None
    assert page._latest_dual_captured_at_ms is None


def test_single_p2_follow_requires_selected_program_role_before_binding(tmp_path):
    page, outputs, transform = _dual_target_page(tmp_path)
    page._latest_dual_state = DualMotionState(
        "tracking", "visual", {"role-a": (5.0, 5.0), "role-b": None}, transform,
    )
    page.follow_p1_combo.setCurrentIndex(page.follow_p1_combo.findData("role-a"))
    page.follow_p2_combo.setCurrentIndex(page.follow_p2_combo.findData("role-b"))
    page.follow_mode_combo.setCurrentIndex(page.follow_mode_combo.findData("single_p2_program"))

    page.start_follow_experiment()

    assert page._follow_runtime is None
    assert outputs == {}
    assert "有效" in page.follow_status_label.text()


def test_follow_initialization_failure_closes_created_output(tmp_path):
    page, _outputs, _transform = _dual_target_page(tmp_path)
    closed = []

    class _Output:
        def close(self):
            closed.append(True)

    page.program_output_factory = lambda _controller: _Output()
    page.follow_p1_combo.setCurrentIndex(page.follow_p1_combo.findData("role-a"))
    page.follow_mode_combo.setCurrentIndex(page.follow_mode_combo.findData("single_p1_program"))
    runtime = page._make_follow_runtime

    def broken_runtime(*args, **kwargs):
        result = runtime(*args, **kwargs)
        result.add_follower = lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("bad role"))
        return result

    page._make_follow_runtime = broken_runtime
    page.start_follow_experiment()

    assert closed == [True]
    assert page._follow_program_output is None
    assert page._follow_runtime is None


def test_single_program_follow_arms_output_after_map_click(tmp_path):
    _app()
    calls = []

    class _Output:
        def start(self): calls.append("start")
        def write(self, vector, *, elapsed_ms): calls.append(("write", vector, elapsed_ms))
        def stop(self): calls.append("stop")

    page = Poe2CaptureTestPage(
        FakeService(), archive=FakeArchive(tmp_path),
        monitor_config=SimpleNamespace(sample_interval_ms=100, binding=None),
        preview_provider=None, program_output_factory=lambda controller: _Output(),
    )
    page._follow_command_arm_delay_ms = 0
    page._follow_foreground_check_override = True
    page.initialize_session()
    page.capture_map()
    page.map_widget.set_image(QPixmap(32, 32))
    transform = SimilarityTransform2D(0, False, 1.0, (0.0, 0.0))
    state = DualMotionState("tracking", "visual", {"role-a": (5.0, 5.0), "role-b": (8.0, 8.0)}, transform)
    page._dual_motion_tracker = object()
    page._dual_map_source_size = (32, 32)
    page._dual_map_transform = transform
    page._dual_follow_reference = SimpleNamespace(wall_layer=np.zeros((32, 32), dtype=np.uint8))
    page._latest_dual_state = state
    page._render_dual_motion_state(state, (32, 32))
    page.follow_p1_combo.setCurrentIndex(page.follow_p1_combo.findData("role-a"))
    page.follow_mode_combo.setCurrentIndex(page.follow_mode_combo.findData("single_p1_program"))

    page.start_follow_experiment()
    assert calls == []
    page._on_follow_map_click(20, 20)

    assert calls[0] == "start"
    assert calls[1][0] == "write"
    page.stop_follow_experiment()
    assert calls[-1] == "stop"


def test_program_follow_waits_six_seconds_before_arm_or_write(tmp_path):
    _app()
    calls = []

    class _Output:
        def start(self): calls.append("start")
        def write(self, vector, *, elapsed_ms): calls.append(("write", vector, elapsed_ms))
        def stop(self): calls.append("stop")

    page = Poe2CaptureTestPage(
        FakeService(), archive=FakeArchive(tmp_path),
        monitor_config=SimpleNamespace(sample_interval_ms=100, binding=None),
        preview_provider=None, program_output_factory=lambda controller: _Output(),
    )
    page._follow_foreground_check_override = True
    page.initialize_session()
    page.capture_map()
    page.map_widget.set_image(QPixmap(32, 32))
    transform = SimilarityTransform2D(0, False, 1.0, (0.0, 0.0))
    state = DualMotionState("tracking", "visual", {"role-a": (5.0, 5.0)}, transform)
    page._dual_motion_tracker = object()
    page._dual_map_source_size = (32, 32)
    page._dual_map_transform = transform
    page._dual_follow_reference = SimpleNamespace(wall_layer=np.zeros((32, 32), dtype=np.uint8))
    page._latest_dual_state = state
    page._render_dual_motion_state(state, (32, 32))
    page.follow_p1_combo.setCurrentIndex(page.follow_p1_combo.findData("role-a"))
    page.follow_mode_combo.setCurrentIndex(page.follow_mode_combo.findData("single_p1_program"))

    page.start_follow_experiment()
    not_before = page._follow_output_not_before_ms
    assert not_before is not None
    assert not page._follow_timer.isActive()
    assert calls == []

    # A map click must not bypass the start-time handoff window.
    page._on_follow_map_click(20, 20)
    assert page._follow_timer.isActive()
    assert calls == []
    assert page._follow_output_not_before_ms == not_before
    assert "等待" in page.follow_status_label.text()

    # Once the gate expires, the normal tick owns arming and writing.
    page._follow_output_not_before_ms = int(time.time() * 1000) - 1
    page._tick_follow_experiment()
    assert calls[0] == "start"
    assert calls[1][0] == "write"
    page.stop_follow_experiment()


def test_program_follow_refreshes_position_from_visual_state_and_releases_at_target(tmp_path):
    _app()
    calls = []

    class _Output:
        def start(self): calls.append("start")
        def write(self, vector, *, elapsed_ms): calls.append(("write", vector, elapsed_ms))
        def stop(self): calls.append("stop")

    page = Poe2CaptureTestPage(
        FakeService(), archive=FakeArchive(tmp_path),
        monitor_config=SimpleNamespace(sample_interval_ms=100, binding=None),
        preview_provider=None, program_output_factory=lambda controller: _Output(),
    )
    page._follow_command_arm_delay_ms = 0
    page._follow_foreground_check_override = True
    page.initialize_session()
    page.capture_map()
    page.map_widget.set_image(QPixmap(32, 32))
    transform = SimilarityTransform2D(0, False, 1.0, (0.0, 0.0))
    page._dual_motion_tracker = object()
    page._dual_map_source_size = (32, 32)
    page._dual_map_transform = transform
    page._dual_follow_reference = SimpleNamespace(wall_layer=np.zeros((32, 32), dtype=np.uint8))
    page._latest_dual_state = DualMotionState("tracking", "visual", {"role-a": (5.0, 5.0)}, transform)
    page._render_dual_motion_state(page._latest_dual_state, (32, 32))
    page.follow_p1_combo.setCurrentIndex(page.follow_p1_combo.findData("role-a"))
    page.follow_mode_combo.setCurrentIndex(page.follow_mode_combo.findData("single_p1_program"))
    page.start_follow_experiment()
    page._on_follow_map_click(20, 20)
    assert page._follow_runtime is not None
    assert page._follow_timer.isActive()

    page._latest_dual_state = DualMotionState("tracking", "visual", {"role-a": (20.0, 20.0)}, transform)
    page._tick_follow_experiment()

    assert page._last_follow_observations["local-device:role-a"].state is FollowState.ARRIVED
    assert calls[-1] == "stop"

    page._latest_dual_state = DualMotionState("tracking", "visual", {"role-a": (20.0, 20.0)}, transform)
    # Pick a destination outside the arrival band so the shared tick has to
    # re-arm the released output for the new target.
    page._on_follow_map_click(30, 30)
    assert "start" in calls[-3:]
    assert any(isinstance(call, tuple) and call[0] == "write" for call in calls[-2:])


def test_dual_program_follow_arms_both_controllers_and_writes_each_route(tmp_path):
    _app()
    outputs = {}

    class _Output:
        def __init__(self, controller):
            self.controller = controller
            self.calls = []
            outputs[controller] = self
        def start(self): self.calls.append("start")
        def write(self, vector, *, elapsed_ms): self.calls.append(("write", vector, elapsed_ms))
        def stop(self): self.calls.append("stop")

    page = Poe2CaptureTestPage(
        FakeService(), archive=FakeArchive(tmp_path),
        monitor_config=SimpleNamespace(sample_interval_ms=100, binding=None),
        preview_provider=None, program_output_factory=_Output,
    )
    page._follow_command_arm_delay_ms = 0
    # These tests use fake output objects and do not launch PoE2.  Explicitly
    # bypass the production foreground gate so the tests exercise follow
    # state transitions rather than the host desktop's current foreground
    # window.
    page._follow_foreground_check_override = True
    page.initialize_session()
    page.capture_map()
    page.map_widget.set_image(QPixmap(32, 32))
    transform = SimilarityTransform2D(0, False, 1.0, (0.0, 0.0))
    state = DualMotionState(
        "tracking", "visual", {"role-a": (5.0, 5.0), "role-b": (8.0, 8.0)}, transform,
    )
    page._dual_motion_tracker = object()
    page._dual_map_source_size = (32, 32)
    page._dual_map_transform = transform
    page._dual_follow_reference = SimpleNamespace(wall_layer=np.zeros((32, 32), dtype=np.uint8))
    page._latest_dual_state = state
    page._render_dual_motion_state(state, (32, 32))
    page.follow_p1_combo.setCurrentIndex(page.follow_p1_combo.findData("role-a"))
    page.follow_p2_combo.setCurrentIndex(page.follow_p2_combo.findData("role-b"))
    page.follow_mode_combo.setCurrentIndex(page.follow_mode_combo.findData("both_program"))

    page.start_follow_experiment()
    page._on_follow_map_click(20, 20)

    assert set(outputs) == {1, 2}
    assert all(output.calls[0] == "start" for output in outputs.values())
    assert all(any(call[0] == "write" for call in output.calls[1:]) for output in outputs.values())
    page.stop_follow_experiment()
    assert all(output.calls[-1] == "stop" for output in outputs.values())


@pytest.mark.parametrize(
    ("mode", "leader_identity", "follower_identity", "controller"),
    [
        ("p1_leads", "role-a", "role-b", 2),
        ("p2_leads", "role-b", "role-a", 1),
    ],
)
def test_live_role_follow_tracks_fresh_leader_and_only_controls_follower(
    tmp_path, mode, leader_identity, follower_identity, controller,
):
    _app()
    outputs = {}

    class _Output:
        def __init__(self, index):
            self.calls = []
            outputs[index] = self

        def start(self): self.calls.append("start")
        def write(self, vector, *, elapsed_ms): self.calls.append(("write", vector, elapsed_ms))
        def stop(self): self.calls.append("stop")

    page = Poe2CaptureTestPage(
        FakeService(), archive=FakeArchive(tmp_path),
        monitor_config=SimpleNamespace(sample_interval_ms=100, binding=None),
        preview_provider=None, program_output_factory=_Output,
    )
    page._follow_command_arm_delay_ms = 0
    page._follow_foreground_check_override = True
    page.initialize_session()
    page.capture_map()
    page.map_widget.set_image(QPixmap(100, 100))
    transform = SimilarityTransform2D(0, False, 1.0, (0.0, 0.0))
    players = {leader_identity: (80.0, 10.0), follower_identity: (10.0, 10.0)}
    state = DualMotionState("tracking", "visual", players, transform)
    page._dual_motion_tracker = object()
    page._dual_map_source_size = (100, 100)
    page._dual_map_transform = transform
    page._dual_follow_reference = SimpleNamespace(wall_layer=np.zeros((100, 100), dtype=np.uint8))
    page._latest_dual_state = state
    captured_at_ms = int(time.time() * 1000)
    page._latest_dual_captured_at_ms = captured_at_ms
    page._render_dual_motion_state(state, (100, 100))
    page.follow_p1_combo.setCurrentIndex(page.follow_p1_combo.findData("role-a"))
    page.follow_p2_combo.setCurrentIndex(page.follow_p2_combo.findData("role-b"))
    page.follow_mode_combo.setCurrentIndex(page.follow_mode_combo.findData(mode))
    assert page.follow_footprint_radius.value() == 3.0

    page.start_follow_experiment()
    _complete_live_follow_cold_start(page)
    captured_at_ms = int(page._latest_dual_captured_at_ms)
    page._tick_follow_experiment()
    runtime = page._follow_runtime
    assert runtime is not None
    assert runtime.footprint_radius == 3.0
    assert runtime.inflate_collision is False
    assert set(outputs) == {controller}
    assert outputs[controller].calls[0] == "start"
    assert runtime.remote.position.role.actor_id == leader_identity
    assert runtime.remote.position.captured_at_ms == captured_at_ms
    assert page._last_follow_observations[f"local-device:{leader_identity}"].state is FollowState.MANUAL

    page._tick_follow_experiment()
    assert runtime.remote.position.captured_at_ms == captured_at_ms
    page._latest_dual_state = DualMotionState(
        "tracking", "visual", {leader_identity: (80.0, 10.0), follower_identity: (70.0, 10.0)}, transform,
    )
    page._latest_dual_captured_at_ms = captured_at_ms + 10
    # This synthetic page state jumps 60 cells in 10 ms. A real visual
    # innovation must reject that; model the separate completed re-anchor.
    page._follow_role_tracker.seed(
        f"local-device:{follower_identity}", runtime.map_identity.map_version,
        (70.0, 10.0), captured_at_ms=captured_at_ms + 10,
    )
    page._tick_follow_experiment()
    assert page._last_follow_observations[f"local-device:{follower_identity}"].state is FollowState.ARRIVED
    assert outputs[controller].calls[-1] == "stop"

    page._latest_dual_state = DualMotionState(
        "tracking", "visual", {leader_identity: (90.0, 10.0), follower_identity: (70.0, 10.0)}, transform,
    )
    page._latest_dual_captured_at_ms = captured_at_ms + 20
    page._follow_role_tracker.seed(
        f"local-device:{leader_identity}", runtime.map_identity.map_version,
        (90.0, 10.0), captured_at_ms=captured_at_ms + 20,
    )
    page._tick_follow_experiment()
    assert outputs[controller].calls[-2] == "start"
    page.stop_follow_experiment()


def test_live_follow_accepts_large_manual_leader_visual_move_without_reanchor(tmp_path):
    page, outputs, transform = _dual_target_page(tmp_path)
    page.follow_p1_combo.setCurrentIndex(page.follow_p1_combo.findData("role-a"))
    page.follow_p2_combo.setCurrentIndex(page.follow_p2_combo.findData("role-b"))
    page.follow_mode_combo.setCurrentIndex(page.follow_mode_combo.findData("p1_leads"))
    # Exercise the steady-state path.  The startup/recovery visual phase is
    # intentionally disabled so this test fails if the manual leader is sent
    # back through the follower command-odometry innovation gate.
    page._follow_visual_phase_grace_ms = 0
    base = int(time.time() * 1000)
    page._latest_dual_state = DualMotionState(
        "tracking", "visual", {"role-a": (25.0, 8.0), "role-b": (5.0, 8.0)}, transform,
    )
    page._latest_dual_captured_at_ms = base

    page.start_follow_experiment()
    _complete_live_follow_cold_start(page)
    base = int(page._latest_dual_captured_at_ms)
    assert page._follow_runtime is not None
    assert outputs[2].calls and outputs[2].calls[0] == "start"

    # A manually controlled leader can legitimately jump much farther than a
    # program pulse.  It must update the target directly instead of entering
    # the follower command-odometry innovation rejection path.
    page._latest_dual_state = DualMotionState(
        "tracking", "visual", {"role-a": (80.0, 55.0), "role-b": (5.0, 8.0)}, transform,
    )
    page._latest_dual_captured_at_ms = base + 100
    page._tick_follow_experiment()

    assert page._follow_runtime is not None
    assert page._follow_runtime.remote.position.position == (80.0, 55.0)
    assert page._follow_sync_phase == "tracking"
    assert page._follow_stop_reason is None
    assert page._dual_motion_restart_pending is None
    page.stop_follow_experiment()


def test_live_role_follow_waits_when_roles_start_together_then_resumes_after_leader_moves(tmp_path):
    page, outputs, transform = _dual_target_page(tmp_path)
    page.follow_p1_combo.setCurrentIndex(page.follow_p1_combo.findData("role-a"))
    page.follow_p2_combo.setCurrentIndex(page.follow_p2_combo.findData("role-b"))
    page.follow_mode_combo.setCurrentIndex(page.follow_mode_combo.findData("p1_leads"))
    now = int(time.time() * 1000)
    page._latest_dual_state = DualMotionState(
        "tracking", "visual", {"role-a": (5.0, 5.0), "role-b": (8.0, 8.0)}, transform,
    )
    page._latest_dual_captured_at_ms = now
    reasons = []
    page._request_live_follow_reanchor = reasons.append

    page.start_follow_experiment()
    _complete_live_follow_cold_start(page)

    # A close initial spawn is a healthy arrival hold: no virtual-gamepad
    # lease or movement should be started, and no relocalization is needed.
    assert outputs[2].calls == []
    assert page._last_follow_observations["local-device:role-b"].state is FollowState.ARRIVED
    assert reasons == []

    # Once the leader has moved beyond the 20-unit resume band, the same
    # runtime must transition to PROGRAM_READY and arm the follower output.
    for index, leader_point in enumerate(((15.0, 5.0), (25.0, 5.0), (30.0, 5.0)), start=1):
        captured_at_ms = now + index * 250
        page._latest_dual_state = DualMotionState(
            "tracking", "visual", {"role-a": leader_point, "role-b": (8.0, 8.0)}, transform,
        )
        page._latest_dual_captured_at_ms = captured_at_ms
        page._follow_role_tracker.seed(
            "local-device:role-a", page._follow_runtime.map_identity.map_version,
            leader_point, captured_at_ms=captured_at_ms,
        )
        page._tick_follow_experiment()
    assert page._last_follow_observations["local-device:role-b"].state is FollowState.PROGRAM_READY
    assert outputs[2].calls[0] == "start"
    assert any(call[0] == "write" for call in outputs[2].calls[1:])
    assert reasons == []
    page.stop_follow_experiment()


def test_live_role_follow_does_not_reanchor_for_occluded_follower_in_arrival_hold(tmp_path):
    page, _outputs, transform = _dual_target_page(tmp_path)
    page.follow_p1_combo.setCurrentIndex(page.follow_p1_combo.findData("role-a"))
    page.follow_p2_combo.setCurrentIndex(page.follow_p2_combo.findData("role-b"))
    page.follow_mode_combo.setCurrentIndex(page.follow_mode_combo.findData("p1_leads"))
    now = int(time.time() * 1000)
    page._latest_dual_state = DualMotionState(
        "tracking", "visual", {"role-a": (5.0, 5.0), "role-b": (8.0, 8.0)}, transform,
    )
    page._latest_dual_captured_at_ms = now
    reasons = []
    page._request_live_follow_reanchor = reasons.append
    page.start_follow_experiment()
    _complete_live_follow_cold_start(page)

    page._latest_dual_state = DualMotionState(
        "degraded", "markers_partial_grace",
        {"role-a": (5.0, 5.0), "role-b": (8.0, 8.0)}, transform,
        wall_quality=1.0,
        diagnostics={"wall_trusted": True, "role_observations": {
            "role-a": {"visible": True, "available": True, "last_seen_at_ms": now + 10,
                       "age_ms": 0, "uncertainty_native": 0.5},
            "role-b": {"visible": False, "available": True, "last_seen_at_ms": now,
                       "age_ms": 10, "uncertainty_native": 1.0},
        }},
    )
    page._latest_dual_captured_at_ms = now + 10
    page._tick_follow_experiment()

    observation = page._last_follow_observations["local-device:role-b"]
    assert observation.reason == "arrival_unconfirmed"
    assert page._is_normal_follow_hold(observation)
    assert reasons == []
    page.stop_follow_experiment()


def test_live_follow_reanchor_uses_page_level_recovery_cooldown(tmp_path):
    page, _outputs, _transform = _dual_target_page(tmp_path)
    now_ms = int(time.time() * 1000)
    calls = []
    page._dual_last_recovery_at_ms = now_ms
    page._save_dual_follow_recovery_context = lambda: calls.append("save")
    page.stop_dual_motion = lambda **_kwargs: calls.append("stop")
    page._start_dual_motion = lambda **_kwargs: calls.append("restart")

    page._request_live_follow_reanchor("command_prediction_unbounded")

    assert calls == ["stop"]
    assert "冷却" in page.follow_status_label.text()


def test_live_follow_reanchor_diagnostic_cannot_abort_recovery(tmp_path, caplog):
    """The recovery diagnostic must not throw before recovery is scheduled."""
    page, _outputs, _transform = _dual_target_page(tmp_path)
    calls = []
    page._follow_last_visual_positions = {"role-b": (12.0, 13.0)}
    page._last_follow_observations = {"role-b": "observation"}
    page._save_dual_follow_recovery_context = lambda: calls.append("save")
    page._start_dual_motion = lambda **kwargs: calls.append(("restart", kwargs))

    with caplog.at_level("WARNING"):
        page._request_live_follow_reanchor("command_prediction_unbounded")

    assert calls == ["save", ("restart", {"recovery": True})]
    assert "step=live_role_follow.reanchor" in caplog.text
    assert "last_visual_positions={'role-b': (12.0, 13.0)}" in caplog.text


def test_live_follow_reanchor_preserves_active_session(tmp_path):
    """Visual recovery must not enter the user-stop lifecycle."""
    page, outputs, transform = _dual_target_page(tmp_path)
    page.follow_p1_combo.setCurrentIndex(page.follow_p1_combo.findData("role-a"))
    page.follow_p2_combo.setCurrentIndex(page.follow_p2_combo.findData("role-b"))
    page.follow_mode_combo.setCurrentIndex(page.follow_mode_combo.findData("p1_leads"))
    page._latest_dual_state = DualMotionState(
        "tracking", "visual", {"role-a": (25.0, 8.0), "role-b": (5.0, 8.0)}, transform,
    )
    page.start_follow_experiment()
    _complete_live_follow_cold_start(page)
    runtime = page._follow_runtime
    session_id = page._follow_session_id
    stop_calls = []
    restart_calls = []
    page.stop_follow_experiment = lambda **kwargs: stop_calls.append(kwargs)
    page._start_dual_motion = lambda **kwargs: restart_calls.append(kwargs)
    page._save_dual_follow_recovery_context = lambda: None

    page._request_live_follow_reanchor("markers_missing")

    assert stop_calls == []
    assert page._follow_runtime is runtime
    assert page._follow_session_id == session_id
    assert page._follow_recovery_pending is True
    assert restart_calls == [{"recovery": True, "preserve_follow": True}]
    assert outputs[2].calls[-1] == "stop"
    page.stop_follow_experiment()


def test_live_follow_reanchor_coalesces_one_visual_failure_episode(tmp_path):
    """A repeated mismatch cannot re-enter recovery on every follow tick."""
    page, _outputs, transform = _dual_target_page(tmp_path)
    page.follow_p1_combo.setCurrentIndex(page.follow_p1_combo.findData("role-a"))
    page.follow_p2_combo.setCurrentIndex(page.follow_p2_combo.findData("role-b"))
    page.follow_mode_combo.setCurrentIndex(page.follow_mode_combo.findData("p1_leads"))
    page._latest_dual_state = DualMotionState(
        "tracking", "visual", {"role-a": (25.0, 8.0), "role-b": (5.0, 8.0)}, transform,
    )
    page._latest_dual_captured_at_ms = int(time.time() * 1000)
    page.start_follow_experiment()
    _complete_live_follow_cold_start(page)

    claims = []
    restarts = []
    page._claim_dual_recovery = lambda *, reason: claims.append(reason) or True
    page._save_dual_follow_recovery_context = lambda: None
    page._start_dual_motion = lambda **kwargs: restarts.append(kwargs)

    for _ in range(100):
        page._request_live_follow_reanchor("repeated_visual_innovation_rejected")

    assert claims == ["follow:repeated_visual_innovation_rejected"]
    assert restarts == [{"recovery": True, "preserve_follow": True}]
    assert page._follow_recovery_episode_active is True
    assert page._follow_recovery_pending is True
    assert page._follow_recovery_episode_suppressed == 99

    page._follow_recovery_pending = False
    page._clear_live_follow_recovery_episode("fresh_sync")
    page._request_live_follow_reanchor("new_visual_failure")
    assert claims == [
        "follow:repeated_visual_innovation_rejected",
        "follow:new_visual_failure",
    ]
    assert len(restarts) == 2
    page.stop_follow_experiment()


def test_live_follow_tick_fault_keeps_session_running(tmp_path):
    """A transient tick fault must not turn an active follow into stopped."""
    page, _outputs, transform = _dual_target_page(tmp_path)
    page.follow_p1_combo.setCurrentIndex(page.follow_p1_combo.findData("role-a"))
    page.follow_p2_combo.setCurrentIndex(page.follow_p2_combo.findData("role-b"))
    page.follow_mode_combo.setCurrentIndex(page.follow_mode_combo.findData("p1_leads"))
    page._latest_dual_state = DualMotionState(
        "tracking", "visual", {"role-a": (25.0, 8.0), "role-b": (5.0, 8.0)}, transform,
    )
    page.start_follow_experiment()
    runtime = page._follow_runtime
    stop_calls = []
    page.stop_follow_experiment = lambda **kwargs: stop_calls.append(kwargs)
    page._tick_follow_experiment_impl = lambda: (_ for _ in ()).throw(
        RuntimeError("synthetic transient fault")
    )

    page._tick_follow_experiment()

    assert stop_calls == []
    assert page._follow_runtime is runtime
    assert page._follow_timer.isActive()
    assert page._follow_recovery_pending is True
    page.stop_follow_experiment = Poe2CaptureTestPage.stop_follow_experiment.__get__(page)
    page.stop_follow_experiment()


def test_preview_rescales_when_panel_grows_without_new_frame(tmp_path):
    app = _app()
    page = Poe2CaptureTestPage(
        FakeService(), archive=FakeArchive(tmp_path),
        monitor_config=SimpleNamespace(sample_interval_ms=100, binding=None),
        preview_provider=None,
    )
    page.resize(1200, 800)
    page.show()
    app.processEvents()
    page._set_preview(page.frame_preview, np.zeros((80, 80, 3), dtype=np.uint8))
    before = page.frame_preview.pixmap().size()
    page.resize(1600, 900)
    app.processEvents()
    assert page.frame_preview.pixmap().width() > before.width(), (
        page.size(), page.main_splitter.sizes(), page.workspace_splitter.sizes(),
        page.preview_splitter.sizes(),
        page.frame_preview.size(),
    )
    assert page.workspace_splitter.count() == 2
    assert page.preview_splitter.count() == 3
    page.close()


def test_live_role_follow_holds_prediction_on_stale_frame_and_recovers_on_new_frame(tmp_path):
    page, outputs, transform = _dual_target_page(tmp_path)
    page.follow_p1_combo.setCurrentIndex(page.follow_p1_combo.findData("role-a"))
    page.follow_p2_combo.setCurrentIndex(page.follow_p2_combo.findData("role-b"))
    page.follow_mode_combo.setCurrentIndex(page.follow_mode_combo.findData("p1_leads"))
    page.follow_footprint_radius.setValue(4.5)
    page._latest_dual_state = DualMotionState(
        "tracking", "visual", {"role-a": (25.0, 8.0), "role-b": (5.0, 8.0)}, transform,
    )
    page.start_follow_experiment()
    _complete_live_follow_cold_start(page)
    assert page._follow_runtime.footprint_radius == 4.5
    assert outputs[2].calls[0] == "start"

    page._latest_dual_captured_at_ms = int(time.time() * 1000) - 1000
    release_calls = []
    original_release_all = page._follow_program_output.release_all
    page._follow_program_output.release_all = lambda: (release_calls.append(True), original_release_all())[1]
    stale_target_time = page._follow_runtime.remote.position.captured_at_ms
    page._tick_follow_experiment()
    assert outputs[2].calls[-1] != "stop"
    assert len(release_calls) == 0
    assert page._follow_runtime.remote.position.captured_at_ms > stale_target_time
    page._tick_follow_experiment()
    assert page._follow_runtime.remote.position.captured_at_ms > stale_target_time
    assert len(release_calls) == 0

    page._latest_dual_captured_at_ms = int(time.time() * 1000)
    page._tick_follow_experiment()
    assert outputs[2].calls[-1][0] == "write"
    target = page._follow_runtime.remote.position
    page._on_follow_map_click(20, 20)
    assert page._follow_runtime.remote.position == target
    page._dual_map_transform = None
    page._tick_follow_experiment()
    assert page._follow_runtime is not None
    assert page._follow_recovery_pending is True
    assert page._follow_timer.isActive()
    assert outputs[2].calls[-1] == "stop"


def test_live_follow_stale_frame_requests_one_recovery_after_stall(tmp_path):
    page, _outputs, transform = _dual_target_page(tmp_path)
    page.follow_p1_combo.setCurrentIndex(page.follow_p1_combo.findData("role-a"))
    page.follow_p2_combo.setCurrentIndex(page.follow_p2_combo.findData("role-b"))
    page.follow_mode_combo.setCurrentIndex(page.follow_mode_combo.findData("p1_leads"))
    now_ms = int(time.time() * 1000)
    page._latest_dual_state = DualMotionState(
        "tracking", "visual", {"role-a": (25.0, 8.0), "role-b": (5.0, 8.0)}, transform,
    )
    page._latest_dual_captured_at_ms = now_ms
    page.start_follow_experiment()
    _complete_live_follow_cold_start(page)
    reasons = []
    page._request_live_follow_reanchor = reasons.append
    page._follow_stale_since_ms = now_ms - page._FOLLOW_STALE_RECOVERY_AFTER_MS - 1
    page._latest_dual_captured_at_ms = now_ms - page._FOLLOW_RUNTIME_MAX_FRAME_AGE_MS - 1

    page._tick_follow_experiment()

    assert reasons == ["visual_frame_stalled"]
    assert page._follow_stale_recovery_requested is True


def test_live_follow_keeps_prediction_when_capture_timestamp_is_missing(tmp_path):
    page, outputs, transform = _dual_target_page(tmp_path)
    page.follow_p1_combo.setCurrentIndex(page.follow_p1_combo.findData("role-a"))
    page.follow_p2_combo.setCurrentIndex(page.follow_p2_combo.findData("role-b"))
    page.follow_mode_combo.setCurrentIndex(page.follow_mode_combo.findData("p1_leads"))
    page._latest_dual_state = DualMotionState(
        "tracking", "visual", {"role-a": (25.0, 8.0), "role-b": (5.0, 8.0)}, transform,
    )
    page._latest_dual_captured_at_ms = int(time.time() * 1000)
    page.start_follow_experiment()
    _complete_live_follow_cold_start(page)

    page._latest_dual_captured_at_ms = None
    page._tick_follow_experiment()

    assert page._follow_runtime is not None
    assert outputs[2].calls[-1] != "stop"
    assert page._last_follow_observations["local-device:role-b"].position is not None
    page.stop_follow_experiment()


def test_shutdown_cancels_follow_recovery_callbacks_and_releases_output(tmp_path, monkeypatch):
    page, outputs, transform = _dual_target_page(tmp_path)
    page.follow_p1_combo.setCurrentIndex(page.follow_p1_combo.findData("role-a"))
    page.follow_p2_combo.setCurrentIndex(page.follow_p2_combo.findData("role-b"))
    page.follow_mode_combo.setCurrentIndex(page.follow_mode_combo.findData("p1_leads"))
    page._latest_dual_state = DualMotionState(
        "tracking", "visual", {"role-a": (25.0, 8.0), "role-b": (5.0, 8.0)}, transform,
    )
    page._latest_dual_captured_at_ms = int(time.time() * 1000)
    page.start_follow_experiment()
    _complete_live_follow_cold_start(page)

    callbacks = []
    monkeypatch.setattr(
        capture_test_page_module.QTimer,
        "singleShot",
        staticmethod(lambda _delay, callback: callbacks.append(callback)),
    )
    page._follow_recovery_pending = True
    page._schedule_live_follow_recovery_retry("test_shutdown")
    page.shutdown()
    for callback in callbacks:
        callback()

    assert page._closing is True
    assert page._follow_runtime is None
    assert not page._follow_timer.isActive()
    assert outputs[2].calls[-1] == "stop"


def test_live_role_follow_releases_on_markerless_warmup_frame(tmp_path):
    page, outputs, transform = _dual_target_page(tmp_path)
    page.follow_p1_combo.setCurrentIndex(page.follow_p1_combo.findData("role-a"))
    page.follow_p2_combo.setCurrentIndex(page.follow_p2_combo.findData("role-b"))
    page.follow_mode_combo.setCurrentIndex(page.follow_mode_combo.findData("p1_leads"))
    page._latest_dual_state = DualMotionState(
        "tracking", "visual", {"role-a": (25.0, 8.0), "role-b": (5.0, 8.0)}, transform,
    )
    page.start_follow_experiment()
    _complete_live_follow_cold_start(page)
    assert outputs[2].calls[0] == "start"

    page._latest_dual_state = DualMotionState(
        "tracking", "markers_missing_grace",
        {"role-a": (25.0, 8.0), "role-b": (5.0, 8.0)}, transform,
        diagnostics={"warmup_assumed_stationary": True, "visible_identities": ()},
    )
    page._latest_dual_captured_at_ms = int(time.time() * 1000)
    page._tick_follow_experiment()

    assert outputs[2].calls[-1] == "stop"
    page.stop_follow_experiment()


def test_live_role_follow_requires_a_fresh_start_frame(tmp_path):
    page, outputs, transform = _dual_target_page(tmp_path)
    page.follow_p1_combo.setCurrentIndex(page.follow_p1_combo.findData("role-a"))
    page.follow_p2_combo.setCurrentIndex(page.follow_p2_combo.findData("role-b"))
    page.follow_mode_combo.setCurrentIndex(page.follow_mode_combo.findData("p1_leads"))
    page._latest_dual_state = DualMotionState(
        "tracking", "visual", {"role-a": (25.0, 8.0), "role-b": (5.0, 8.0)}, transform,
    )
    page._latest_dual_captured_at_ms = int(time.time() * 1000) - 400

    page.start_follow_experiment()

    assert page._follow_runtime is None
    assert outputs == {}
    assert "新鲜" in page.follow_status_label.text()


def test_live_role_follow_ignores_transient_visual_rejections_during_start_phase(tmp_path):
    page, _outputs, transform = _dual_target_page(tmp_path)
    page.follow_p1_combo.setCurrentIndex(page.follow_p1_combo.findData("role-a"))
    page.follow_p2_combo.setCurrentIndex(page.follow_p2_combo.findData("role-b"))
    page.follow_mode_combo.setCurrentIndex(page.follow_mode_combo.findData("p1_leads"))
    initial = int(time.time() * 1000)
    page._latest_dual_state = DualMotionState(
        "tracking", "visual", {"role-a": (25.0, 8.0), "role-b": (5.0, 8.0)}, transform,
    )
    page._latest_dual_captured_at_ms = initial
    page.start_follow_experiment()
    reasons = []
    page._request_live_follow_reanchor = reasons.append

    for captured_at_ms in (initial + 1, initial + 2):
        page._latest_dual_captured_at_ms = captured_at_ms
        page._latest_dual_state = DualMotionState(
            "tracking", "visual", {"role-a": (25.0, 8.0), "role-b": (900.0, 8.0)}, transform,
        )
        page._tick_follow_experiment()

    assert reasons == []
    page.stop_follow_experiment()


def test_dual_marker_loss_saves_one_bounded_evidence_bundle_per_transition(tmp_path):
    page, _outputs, transform = _dual_target_page(tmp_path)
    state = DualMotionState(
        "degraded", "markers_partial_grace", {"role-a": (5, 5), "role-b": (8, 8)},
        transform, diagnostics={"missing_identities": ("role-b",)},
    )
    raw = np.zeros((20, 20, 3), dtype=np.uint8)
    page._record_dual_observation_evidence(state, raw, (), 123)
    page._record_dual_observation_evidence(state, raw, (), 124)
    assert len(list((tmp_path / "occlusion_diagnostics").iterdir())) == 1
    page.stop_dual_motion()


def test_overwritten_recovery_revision_is_handled_before_follow_resume(tmp_path):
    page, _outputs, transform = _dual_target_page(tmp_path)
    calls = []
    state = DualMotionState(
        "tracking", "visual", {"role-a": (5, 5), "role-b": (8, 8)}, transform,
        recovery_requested=False, recovery_revision=1,
    )
    result = SimpleNamespace(
        state=state, captured_at_ms=int(time.time() * 1000), raw=None, combined=None,
        candidates=(), capture_ms=0, recognition_ms=0, tracking_ms=0,
    )

    class _Worker:
        dropped_results = 1
        completed_frames = 2

        def __init__(self):
            self.latest = result
            self.revision = 1

        def take_latest(self):
            latest, self.latest = self.latest, None
            return latest

        def take_pending_recovery_revision(self):
            revision, self.revision = self.revision, 0
            return revision

    page._dual_motion_worker = _Worker()
    page._dual_last_ui_render_at = time.perf_counter()
    page._maybe_resume_dual_follow_after_relocalization = lambda: calls.append("resume")
    page.stop_dual_motion = lambda **_kwargs: calls.append("stop")
    page._start_dual_motion = lambda *, recovery: calls.append(("restart", recovery))

    page._drain_dual_motion_worker()
    page._drain_dual_motion_worker()
    assert calls == ["stop", ("restart", True)]


def test_persistent_recovery_state_recovers_when_edge_flag_was_overwritten(tmp_path):
    page, _outputs, transform = _dual_target_page(tmp_path)
    calls = []
    state = DualMotionState(
        "recovery_required", "markers_missing", {}, transform,
        recovery_requested=False, recovery_revision=4,
    )
    result = SimpleNamespace(
        state=state, captured_at_ms=int(time.time() * 1000), raw=None, combined=None,
        candidates=(), capture_ms=0, recognition_ms=0, tracking_ms=0,
    )

    class _Worker:
        dropped_results = 0
        completed_frames = 1

        def __init__(self):
            self.latest = result

        def take_latest(self):
            latest, self.latest = self.latest, None
            return latest

        def take_pending_recovery_revision(self):
            return 0

    page._dual_motion_worker = _Worker()
    page._dual_last_ui_render_at = time.perf_counter()
    page.stop_dual_motion = lambda **_kwargs: calls.append("stop")
    page._start_dual_motion = lambda *, recovery: calls.append(("restart", recovery))

    page._drain_dual_motion_worker()
    page._drain_dual_motion_worker()
    assert calls == ["stop", ("restart", True)]


@pytest.mark.parametrize("missing_role,mode,controller", [
    ("role-a", "p1_leads", 2),
    ("role-b", "p1_leads", 2),
    ("role-b", "p2_leads", 1),
])
def test_live_follow_continues_only_with_bounded_role_estimate(
    tmp_path, missing_role, mode, controller,
):
    page, outputs, transform = _dual_target_page(tmp_path)
    page.follow_p1_combo.setCurrentIndex(page.follow_p1_combo.findData("role-a"))
    page.follow_p2_combo.setCurrentIndex(page.follow_p2_combo.findData("role-b"))
    page.follow_mode_combo.setCurrentIndex(page.follow_mode_combo.findData(mode))
    page._latest_dual_state = DualMotionState(
        "tracking", "visual", {"role-a": (25.0, 8.0), "role-b": (5.0, 8.0)}, transform,
    )
    page.start_follow_experiment()
    _complete_live_follow_cold_start(page)
    now = int(time.time() * 1000)
    role_info = {
        role: {
            "visible": role != missing_role,
            "available": True,
            "last_seen_at_ms": now - (400 if role == missing_role else 0),
            "age_ms": 400 if role == missing_role else 0,
            "uncertainty_native": 2.3 if role == missing_role else 0.5,
        }
        for role in ("role-a", "role-b")
    }
    page._latest_dual_state = DualMotionState(
        "degraded", "markers_partial_grace",
        {"role-a": (25.0, 8.0), "role-b": (5.0, 8.0)}, transform,
        wall_quality=1.0,
        diagnostics={"wall_trusted": True, "role_observations": role_info},
    )
    page._latest_dual_captured_at_ms = now
    page._tick_follow_experiment()
    assert outputs[controller].calls[-1] != "stop"

    role_info[missing_role] = {**role_info[missing_role], "available": False}
    page._latest_dual_state = DualMotionState(
        "degraded", "markers_missing", {"role-a": (25.0, 8.0), "role-b": (5.0, 8.0)},
        transform, wall_quality=1.0,
        diagnostics={"wall_trusted": True, "role_observations": role_info},
    )
    page._tick_follow_experiment()
    assert outputs[controller].calls[-1] != "stop"
    page.stop_follow_experiment()


def test_live_follow_uses_acknowledged_motion_after_program_marker_loss(tmp_path):
    page, outputs, transform = _dual_target_page(tmp_path)
    page.follow_p1_combo.setCurrentIndex(page.follow_p1_combo.findData("role-a"))
    page.follow_p2_combo.setCurrentIndex(page.follow_p2_combo.findData("role-b"))
    page.follow_mode_combo.setCurrentIndex(page.follow_mode_combo.findData("p1_leads"))
    now = int(time.time() * 1000)
    page._latest_dual_state = DualMotionState(
        "tracking", "visual", {"role-a": (25.0, 8.0), "role-b": (5.0, 8.0)}, transform,
    )
    page._latest_dual_captured_at_ms = now

    class _ReceiptOutput:
        def __init__(self, controller):
            self.calls = []
            outputs[controller] = self
        def start(self): self.calls.append("start")
        def write(self, vector, *, elapsed_ms):
            self.calls.append(("write", vector, elapsed_ms))
            return SimpleNamespace(
                accepted_at_ms=int(time.time() * 1000) - 80,
                effective_input_vector=(0.5, 0.0), ttl_ms=80,
                effective_axes=(8192, 8192),
            )
        def stop(self): self.calls.append("stop")

    page.program_output_factory = _ReceiptOutput
    page.start_follow_experiment()
    _complete_live_follow_cold_start(page)
    role = RoleId("local-device", "role-b")
    page._follow_role_tracker.seed(role.key, page._follow_runtime.map_identity.map_version,
                                   (5.0, 8.0), captured_at_ms=now - 2200)
    page._follow_role_tracker.record_output(
        role.key, (0.5, 0.0), accepted_at_ms=now - 80, ttl_ms=80,
    )
    role_info = {
        "role-a": {"visible": True, "available": True, "last_seen_at_ms": now,
                   "age_ms": 0, "uncertainty_native": 0.5},
        "role-b": {"visible": False, "available": False, "last_seen_at_ms": now - 2200,
                   "age_ms": 2200, "uncertainty_native": 12.0},
    }
    page._latest_dual_state = DualMotionState(
        "degraded", "markers_missing", {"role-a": (25.0, 8.0), "role-b": (5.0, 8.0)},
        transform, wall_quality=1.0,
        diagnostics={"wall_trusted": True, "role_observations": role_info},
    )
    page._latest_dual_captured_at_ms = int(time.time() * 1000)
    page._tick_follow_experiment()
    follower = page._follow_runtime._followers[role.key]
    assert follower.position.source == "command_prediction"
    assert follower.position.position[0] > 5.0
    displayed = dict(page.map_widget.overlay_label._players)
    assert displayed["role-b"][0] > 5.0
    assert page.map_widget.overlay_label._candidates
    assert outputs[2].calls[-1] != "stop"
    assert page._last_follow_observations[role.key].diagnostics["no_progress_ticks"] <= 1
    page.stop_follow_experiment()


def test_live_follow_requests_reanchor_after_repeated_visual_innovation_rejection(tmp_path):
    page, _outputs, transform = _dual_target_page(tmp_path)
    page.follow_p1_combo.setCurrentIndex(page.follow_p1_combo.findData("role-a"))
    page.follow_p2_combo.setCurrentIndex(page.follow_p2_combo.findData("role-b"))
    page.follow_mode_combo.setCurrentIndex(page.follow_mode_combo.findData("p1_leads"))
    page._latest_dual_state = DualMotionState(
        "tracking", "visual", {"role-a": (25.0, 8.0), "role-b": (5.0, 8.0)}, transform,
    )
    initial = int(time.time() * 1000)
    page._latest_dual_captured_at_ms = initial
    page._follow_visual_phase_grace_ms = 0
    page.start_follow_experiment()
    _complete_live_follow_cold_start(page)
    # Re-anchor the synthetic tracker after the Qt cold-start helper so the
    # test does not accidentally enter the unrelated stale-frame branch.
    sync_at = int(time.time() * 1000)
    page._follow_role_tracker.seed(
        "local-device:role-b", page._follow_runtime.map_identity.map_version,
        (5.0, 8.0), captured_at_ms=sync_at,
    )
    page._follow_last_visual_at_ms["local-device:role-b"] = sync_at
    reasons = []
    page._request_live_follow_reanchor = reasons.append
    for index in (2, 3, 4):
        # Keep the synthetic frame fresh; this test isolates repeated
        # innovation rejection from the separate stale-frame recovery gate.
        page._latest_dual_captured_at_ms = int(time.time() * 1000) + index
        page._latest_dual_state = DualMotionState(
            "tracking", "visual", {"role-a": (25.0, 8.0), "role-b": (900.0, 8.0)}, transform,
        )
        page._tick_follow_experiment()
    assert reasons == ["repeated_visual_innovation_rejected"]
    page.stop_follow_experiment()


def test_live_follow_rebases_continuous_visual_step_when_speed_prediction_is_high(tmp_path):
    page, _outputs, transform = _dual_target_page(tmp_path)
    page.follow_p1_combo.setCurrentIndex(page.follow_p1_combo.findData("role-a"))
    page.follow_p2_combo.setCurrentIndex(page.follow_p2_combo.findData("role-b"))
    page.follow_mode_combo.setCurrentIndex(page.follow_mode_combo.findData("p1_leads"))
    initial = int(time.time() * 1000)
    page._follow_visual_phase_grace_ms = 0
    page._latest_dual_state = DualMotionState(
        "tracking", "visual", {"role-a": (25.0, 8.0), "role-b": (5.0, 8.0)}, transform,
    )
    page._latest_dual_captured_at_ms = initial
    page.start_follow_experiment()
    _complete_live_follow_cold_start(page)
    # The helper may advance the synthetic capture clock to keep the frame
    # fresh under a busy Qt suite; use that accepted sync timestamp below.
    initial = int(page._latest_dual_captured_at_ms)
    assert page._follow_last_visual_positions == {
        "local-device:role-a": (25.0, 8.0),
        "local-device:role-b": (5.0, 8.0),
    }
    assert set(page._follow_last_visual_at_ms) == {
        "local-device:role-a", "local-device:role-b",
    }
    tracker = page._follow_role_tracker
    assert tracker is not None
    tracker.record_output(
        "local-device:role-b", (1.0, 0.0), accepted_at_ms=initial + 2, ttl_ms=220,
    )
    reasons = []
    page._request_live_follow_reanchor = reasons.append
    page._latest_dual_state = DualMotionState(
        "tracking", "visual", {"role-a": (25.0, 8.0), "role-b": (7.0, 12.0)}, transform,
    )
    page._latest_dual_captured_at_ms = initial + 202
    page._tick_follow_experiment()

    assert reasons == []
    assert page._follow_rejected_visual == {}
    assert tracker.diagnostics(
        "local-device:role-b", now_ms=initial + 202,
    )["estimated_speed"] == pytest.approx(4.47213595 / 0.202, rel=0.05)
    page.stop_follow_experiment()


def test_live_follow_holds_hidden_manual_leader_without_inventing_motion(tmp_path):
    page, outputs, transform = _dual_target_page(tmp_path)
    page.follow_p1_combo.setCurrentIndex(page.follow_p1_combo.findData("role-a"))
    page.follow_p2_combo.setCurrentIndex(page.follow_p2_combo.findData("role-b"))
    page.follow_mode_combo.setCurrentIndex(page.follow_mode_combo.findData("p1_leads"))
    page._latest_dual_state = DualMotionState(
        "tracking", "visual", {"role-a": (25.0, 8.0), "role-b": (5.0, 8.0)}, transform,
    )
    page._latest_dual_captured_at_ms = int(time.time() * 1000)
    page.start_follow_experiment()
    _complete_live_follow_cold_start(page)
    previous_target = page._follow_runtime.remote.position.position
    now = int(time.time() * 1000)
    page._latest_dual_state = DualMotionState(
        "degraded", "markers_partial_grace",
        {"role-a": (999.0, 999.0), "role-b": (5.0, 8.0)}, transform,
        wall_quality=1.0,
        diagnostics={"wall_trusted": True, "role_observations": {
            "role-a": {"visible": False, "available": True, "last_seen_at_ms": now - 300,
                       "age_ms": 300, "uncertainty_native": 2.0},
            "role-b": {"visible": True, "available": True, "last_seen_at_ms": now,
                       "age_ms": 0, "uncertainty_native": 0.5},
        }},
    )
    page._latest_dual_captured_at_ms = now
    page._tick_follow_experiment()
    assert page._follow_runtime.remote.position.position == previous_target
    assert page._follow_runtime.remote.position.source == "target_hold"
    assert outputs[2].calls[-1] != "stop"
    page.stop_follow_experiment()


def test_live_role_follow_relocalization_resumes_from_fresh_role_frame(tmp_path):
    page, outputs, transform = _dual_target_page(tmp_path)
    page.follow_p1_combo.setCurrentIndex(page.follow_p1_combo.findData("role-a"))
    page.follow_p2_combo.setCurrentIndex(page.follow_p2_combo.findData("role-b"))
    page.follow_mode_combo.setCurrentIndex(page.follow_mode_combo.findData("p1_leads"))
    page.follow_footprint_radius.setValue(4.0)
    page.start_follow_experiment()
    page._save_dual_follow_recovery_context()
    assert page._dual_recovery_follow_target_source is None
    assert page._dual_recovery_follow_live is True
    page.stop_follow_experiment(_preserve_recovery=True)

    page._latest_dual_state = DualMotionState(
        "tracking", "visual", {"role-a": (25.0, 8.0), "role-b": (5.0, 8.0)}, transform,
    )
    page._latest_dual_captured_at_ms = int(time.time() * 1000)
    page._maybe_resume_dual_follow_after_relocalization()
    assert page._follow_runtime is not None
    assert page._follow_runtime.remote.position.role.actor_id == "role-a"
    assert page._follow_runtime.remote.position.position == (25.0, 8.0)
    assert page._follow_runtime.footprint_radius == 4.0
    assert outputs[2].calls == []
    _complete_live_follow_cold_start(page)
    assert outputs[2].calls[0] == "start"
    assert page._dual_recovery_follow_live is False
    page.stop_follow_experiment()


def test_live_role_follow_relocalization_reanchors_in_place(tmp_path):
    """A fresh recovery frame resumes the same live-follow session."""
    page, outputs, transform = _dual_target_page(tmp_path)
    page.follow_p1_combo.setCurrentIndex(page.follow_p1_combo.findData("role-a"))
    page.follow_p2_combo.setCurrentIndex(page.follow_p2_combo.findData("role-b"))
    page.follow_mode_combo.setCurrentIndex(page.follow_mode_combo.findData("p1_leads"))
    page._latest_dual_state = DualMotionState(
        "tracking", "visual", {"role-a": (25.0, 8.0), "role-b": (5.0, 8.0)}, transform,
    )
    page._latest_dual_captured_at_ms = int(time.time() * 1000)
    page.start_follow_experiment()
    _complete_live_follow_cold_start(page)
    runtime = page._follow_runtime
    session_id = page._follow_session_id
    page._save_dual_follow_recovery_context()
    page._follow_recovery_pending = True
    page._latest_dual_state = DualMotionState(
        "tracking", "relocalized", {"role-a": (26.0, 9.0), "role-b": (6.0, 9.0)}, transform,
    )
    page._latest_dual_captured_at_ms = int(time.time() * 1000)

    page._maybe_resume_dual_follow_after_relocalization()

    assert page._follow_runtime is runtime
    assert page._follow_session_id == session_id
    assert page._follow_recovery_pending is False
    assert page._dual_recovery_follow_live is False
    assert outputs[2].calls.count("start") == 1
    page.stop_follow_experiment()


def test_live_role_follow_relocalization_accepts_wall_trusted_degraded_frame(tmp_path):
    """A bounded marker estimate must be enough to resume after re-anchor."""
    page, outputs, transform = _dual_target_page(tmp_path)
    page.follow_p1_combo.setCurrentIndex(page.follow_p1_combo.findData("role-a"))
    page.follow_p2_combo.setCurrentIndex(page.follow_p2_combo.findData("role-b"))
    page.follow_mode_combo.setCurrentIndex(page.follow_mode_combo.findData("p1_leads"))
    initial = int(time.time() * 1000)
    page._latest_dual_state = DualMotionState(
        "tracking", "visual", {"role-a": (25.0, 8.0), "role-b": (5.0, 8.0)}, transform,
    )
    page._latest_dual_captured_at_ms = initial
    page.start_follow_experiment()
    _complete_live_follow_cold_start(page)
    runtime = page._follow_runtime
    page._save_dual_follow_recovery_context()
    page._follow_recovery_pending = True
    now = int(time.time() * 1000)
    page._latest_dual_state = DualMotionState(
        "degraded", "markers_partial_grace",
        {"role-a": (25.0, 8.0), "role-b": (6.0, 9.0)}, transform,
        wall_quality=1.0,
        diagnostics={"wall_trusted": True, "role_observations": {
            "role-a": {"visible": True, "available": True, "age_ms": 0,
                       "uncertainty_native": 0.5},
            "role-b": {"visible": False, "available": True, "age_ms": 180,
                       "uncertainty_native": 2.0},
        }},
    )
    page._latest_dual_captured_at_ms = now

    page._maybe_resume_dual_follow_after_relocalization()

    assert page._follow_recovery_pending is False
    assert page._follow_runtime is runtime
    assert outputs[2].calls.count("start") == 1
    page.stop_follow_experiment()


def test_live_role_follow_rebuilds_from_wall_trusted_degraded_recovery_frame(tmp_path):
    """A degraded first recovery frame must not strand a rebuilt session."""
    page, _outputs, transform = _dual_target_page(tmp_path)
    page.follow_p1_combo.setCurrentIndex(page.follow_p1_combo.findData("role-a"))
    page.follow_p2_combo.setCurrentIndex(page.follow_p2_combo.findData("role-b"))
    page.follow_mode_combo.setCurrentIndex(page.follow_mode_combo.findData("p1_leads"))
    initial = int(time.time() * 1000)
    page._latest_dual_state = DualMotionState(
        "tracking", "visual", {"role-a": (25.0, 8.0), "role-b": (5.0, 8.0)}, transform,
    )
    page._latest_dual_captured_at_ms = initial
    page.start_follow_experiment()
    page._save_dual_follow_recovery_context()
    page.stop_follow_experiment(_preserve_recovery=True)
    now = int(time.time() * 1000)
    page._latest_dual_state = DualMotionState(
        "degraded", "markers_partial_grace",
        {"role-a": (26.0, 9.0), "role-b": (6.0, 9.0)}, transform,
        wall_quality=1.0,
        diagnostics={"wall_trusted": True},
    )
    page._latest_dual_captured_at_ms = now

    page._maybe_resume_dual_follow_after_relocalization()

    assert page._follow_runtime is not None
    assert page._follow_sync_phase == "cold_start" or page._follow_sync_phase == "recovery_sync"
    page.stop_follow_experiment()


def test_live_role_follow_keeps_recovery_context_until_frame_is_fresh_enough(tmp_path):
    """A stale recovery frame must wait instead of consuming the resume context."""
    page, _outputs, transform = _dual_target_page(tmp_path)
    page.follow_p1_combo.setCurrentIndex(page.follow_p1_combo.findData("role-a"))
    page.follow_p2_combo.setCurrentIndex(page.follow_p2_combo.findData("role-b"))
    page.follow_mode_combo.setCurrentIndex(page.follow_mode_combo.findData("p1_leads"))
    initial = int(time.time() * 1000)
    page._latest_dual_state = DualMotionState(
        "tracking", "visual", {"role-a": (25.0, 8.0), "role-b": (5.0, 8.0)}, transform,
    )
    page._latest_dual_captured_at_ms = initial
    page.start_follow_experiment()
    page._save_dual_follow_recovery_context()
    page.stop_follow_experiment(_preserve_recovery=True)

    stale = int(time.time() * 1000) - page._FOLLOW_START_MAX_FRAME_AGE_MS - 1
    page._latest_dual_state = DualMotionState(
        "tracking", "visual", {"role-a": (26.0, 9.0), "role-b": (6.0, 9.0)}, transform,
    )
    page._latest_dual_captured_at_ms = stale
    page._maybe_resume_dual_follow_after_relocalization()

    assert page._follow_runtime is None
    assert page._dual_recovery_follow_live is True

    page._latest_dual_captured_at_ms = int(time.time() * 1000)
    page._maybe_resume_dual_follow_after_relocalization()
    assert page._follow_runtime is not None
    page.stop_follow_experiment()


def test_click_follow_recovery_uses_runtime_frame_ttl(tmp_path):
    """A click-follow recovery frame must satisfy the same 700ms runtime TTL."""
    page, _outputs, transform = _dual_target_page(tmp_path)
    page.follow_p1_combo.setCurrentIndex(page.follow_p1_combo.findData("role-a"))
    page.follow_p2_combo.setCurrentIndex(page.follow_p2_combo.findData("role-b"))
    page.follow_mode_combo.setCurrentIndex(page.follow_mode_combo.findData("both"))
    page.start_follow_experiment()
    page._on_follow_map_click(20, 20)
    page._save_dual_follow_recovery_context()
    page.stop_follow_experiment(_preserve_recovery=True)

    page._latest_dual_state = DualMotionState(
        "tracking", "visual", {"role-a": (26.0, 9.0), "role-b": (6.0, 9.0)}, transform,
    )
    stale = int(time.time() * 1000) - page._FOLLOW_RUNTIME_MAX_FRAME_AGE_MS - 1
    page._latest_dual_captured_at_ms = stale
    page._maybe_resume_dual_follow_after_relocalization()

    assert page._follow_runtime is None
    assert page._dual_recovery_follow_target_source == (20.0, 20.0)

    page._latest_dual_captured_at_ms = int(time.time() * 1000)
    page._maybe_resume_dual_follow_after_relocalization()
    assert page._follow_runtime is not None
    page.stop_follow_experiment()


def _dual_target_page(tmp_path):
    _app()
    outputs = {}

    class _Output:
        def __init__(self, controller):
            self.calls = []
            outputs[controller] = self

        def start(self): self.calls.append("start")
        def write(self, vector, *, elapsed_ms): self.calls.append(("write", vector, elapsed_ms))
        def stop(self): self.calls.append("stop")

    page = Poe2CaptureTestPage(
        FakeService(), archive=FakeArchive(tmp_path),
        monitor_config=SimpleNamespace(sample_interval_ms=100, binding=None),
        preview_provider=None, program_output_factory=_Output,
    )
    page._follow_command_arm_delay_ms = 0
    page._follow_foreground_check_override = True
    page.initialize_session()
    page.capture_map()
    page.map_widget.set_image(QPixmap(32, 32))
    transform = SimilarityTransform2D(0, False, 1.0, (0.0, 0.0))
    state = DualMotionState(
        "tracking", "visual", {"role-a": (5.0, 5.0), "role-b": (8.0, 8.0)}, transform,
    )
    page._dual_motion_tracker = object()
    page._dual_map_source_size = (32, 32)
    page._dual_map_transform = transform
    cast(Any, page)._dual_follow_reference = SimpleNamespace(
        wall_layer=np.zeros((32, 32), dtype=np.uint8),
    )
    page._latest_dual_state = state
    page._latest_dual_captured_at_ms = int(time.time() * 1000)
    page._render_dual_motion_state(state, (32, 32))
    page.dual_target_p1_combo.setCurrentIndex(page.dual_target_p1_combo.findData("role-a"))
    page.dual_target_p2_combo.setCurrentIndex(page.dual_target_p2_combo.findData("role-b"))
    return page, outputs, transform


def _complete_live_follow_cold_start(page):
    """Deliver one post-arm visual frame for the live-follow state machine."""
    baseline = page._follow_sync_baseline_captured_at_ms
    assert baseline is not None
    # The production gate measures age against the wall clock.  A synthetic
    # ``baseline + 1`` frame becomes stale when the test suite is busy before
    # the helper runs, so use a strictly newer *current* capture timestamp.
    page._latest_dual_captured_at_ms = max(int(baseline) + 1, int(time.time() * 1000))
    page._tick_follow_experiment()


def test_live_follow_waits_for_game_foreground_without_releasing_every_tick(tmp_path):
    page, outputs, _transform = _dual_target_page(tmp_path)
    page.follow_p1_combo.setCurrentIndex(page.follow_p1_combo.findData("role-a"))
    page.follow_p2_combo.setCurrentIndex(page.follow_p2_combo.findData("role-b"))
    page.follow_mode_combo.setCurrentIndex(page.follow_mode_combo.findData("p1_leads"))

    # The helper normally bypasses the production gate.  Turn it off to model
    # the workbench being foreground when the user clicks Start.
    page._follow_foreground_check_override = False
    page.start_follow_experiment()
    assert outputs[2].calls == []
    assert "等待 PoE2" in page.follow_status_label.text()

    # Repeated timer ticks must not repeatedly release the same lease or arm
    # the program output.  The fake output has no calls at all at this point.
    page._tick_follow_experiment()
    assert outputs[2].calls == []

    # Once focus returns, a strictly newer visual frame crosses the cold-start
    # barrier and the first program pulse may be armed.
    page._follow_foreground_check_override = True
    baseline = page._follow_sync_baseline_captured_at_ms
    assert baseline is not None
    page._latest_dual_state = DualMotionState(
        "tracking", "visual", {"role-a": (30.0, 5.0), "role-b": (5.0, 5.0)}, _transform,
    )
    page._latest_dual_captured_at_ms = int(baseline) + 1
    page._tick_follow_experiment()
    assert outputs[2].calls[0] == "start"


def test_live_follow_publishes_role_scoped_prediction_and_clears_worker_on_stop(tmp_path):
    page, _outputs, transform = _dual_target_page(tmp_path)
    page.follow_p1_combo.setCurrentIndex(page.follow_p1_combo.findData("role-a"))
    page.follow_p2_combo.setCurrentIndex(page.follow_p2_combo.findData("role-b"))
    page.follow_mode_combo.setCurrentIndex(page.follow_mode_combo.findData("p1_leads"))
    page._latest_dual_state = DualMotionState(
        "tracking", "visual", {"role-a": (25.0, 8.0), "role-b": (5.0, 8.0)}, transform,
    )
    page._latest_dual_captured_at_ms = int(time.time() * 1000)
    page.start_follow_experiment()
    _complete_live_follow_cold_start(page)
    assert page._follow_runtime is not None
    now = int(time.time() * 1000)
    page._follow_role_tracker.record_output(
        "local-device:role-b", (0.5, 0.0), accepted_at_ms=now, ttl_ms=100,
    )
    messages = []
    page._dual_motion_worker = SimpleNamespace(
        generation=9,
        set_prediction_hints=lambda hints, *, generation: messages.append((hints, generation)),
    )
    page._publish_follow_prediction_hints()
    assert messages[-1][1] == 9
    assert set(messages[-1][0]) == {"role-a", "role-b"}
    assert messages[-1][0]["role-b"][0] >= 5.0
    assert messages[-1][0]["role-a"][0:2] == (25.0, 8.0)
    page.stop_follow_experiment()
    assert messages[-1] == ({}, 9)
    page._dual_motion_worker = None


def test_live_follow_does_not_reanchor_on_first_frame_command_latency(tmp_path):
    page, _outputs, transform = _dual_target_page(tmp_path)
    page.follow_p1_combo.setCurrentIndex(page.follow_p1_combo.findData("role-a"))
    page.follow_p2_combo.setCurrentIndex(page.follow_p2_combo.findData("role-b"))
    page.follow_mode_combo.setCurrentIndex(page.follow_mode_combo.findData("p1_leads"))
    base = int(time.time() * 1000) - 231
    page._latest_dual_state = DualMotionState(
        "tracking", "visual", {"role-a": (25.0, 8.0), "role-b": (5.0, 8.0)}, transform,
    )
    page._latest_dual_captured_at_ms = base
    page.start_follow_experiment()
    tracker = page._follow_role_tracker
    assert tracker is not None
    tracker.record_output(
        "local-device:role-b", (0.1, 0.64), accepted_at_ms=base, ttl_ms=160,
    )
    reasons = []
    page._request_live_follow_reanchor = reasons.append
    page._latest_dual_state = DualMotionState(
        "tracking", "visual", {"role-a": (25.0, 8.0), "role-b": (5.0, 8.0)}, transform,
    )
    page._latest_dual_captured_at_ms = base + 231
    page._tick_follow_experiment()
    assert reasons == []
    assert page._follow_runtime is not None
    assert page._follow_rejected_visual == {}
    page.stop_follow_experiment()


def test_live_follow_does_not_count_the_same_rejected_visual_frame_twice(tmp_path):
    page, _outputs, transform = _dual_target_page(tmp_path)
    page.follow_p1_combo.setCurrentIndex(page.follow_p1_combo.findData("role-a"))
    page.follow_p2_combo.setCurrentIndex(page.follow_p2_combo.findData("role-b"))
    page.follow_mode_combo.setCurrentIndex(page.follow_mode_combo.findData("p1_leads"))
    # Disable the startup pulse grace window; this test exercises the steady
    # innovation rejection counter rather than command-latency handling.
    page._follow_visual_phase_grace_ms = 0
    page._latest_dual_state = DualMotionState(
        "tracking", "visual", {"role-a": (25.0, 8.0), "role-b": (5.0, 8.0)}, transform,
    )
    page._latest_dual_captured_at_ms = int(time.time() * 1000)
    page.start_follow_experiment()
    _complete_live_follow_cold_start(page)

    # A large jump is a genuine innovation rejection.  Re-delivering the
    # same capture timestamp on the next timer tick must not turn that one
    # frame into a repeated-failure episode.
    reasons = []
    page._request_live_follow_reanchor = reasons.append
    baseline = page._follow_sync_baseline_captured_at_ms
    assert baseline is not None
    # Use a fresh capture clock for the synthetic jump.  The rejection test
    # is about innovation, not about the independent 700ms frame-age gate.
    rejected_capture = int(time.time() * 1000)
    page._latest_dual_state = DualMotionState(
        "tracking", "visual", {"role-a": (25.0, 8.0), "role-b": (120.0, 120.0)}, transform,
    )
    page._latest_dual_captured_at_ms = rejected_capture
    page._tick_follow_experiment()
    assert page._follow_rejected_visual.get("local-device:role-b") == 1
    assert reasons == []

    page._tick_follow_experiment()
    assert page._follow_rejected_visual.get("local-device:role-b") == 1
    assert reasons == []
    assert page._follow_runtime is not None
    page.stop_follow_experiment()


def test_live_follow_rebases_a_small_step_after_a_delayed_but_fresh_frame(tmp_path):
    page, _outputs, transform = _dual_target_page(tmp_path)
    page.follow_p1_combo.setCurrentIndex(page.follow_p1_combo.findData("role-a"))
    page.follow_p2_combo.setCurrentIndex(page.follow_p2_combo.findData("role-b"))
    page.follow_mode_combo.setCurrentIndex(page.follow_mode_combo.findData("p1_leads"))
    now = int(time.time() * 1000)
    page._latest_dual_state = DualMotionState(
        "tracking", "visual", {"role-a": (25.0, 8.0), "role-b": (5.0, 8.0)}, transform,
    )
    page._latest_dual_captured_at_ms = now
    page.start_follow_experiment()
    _complete_live_follow_cold_start(page)

    tracker = page._follow_role_tracker
    assert tracker is not None
    role_key = "local-device:role-b"
    delayed_anchor = now - 1_800
    tracker.seed(role_key, page._follow_runtime.map_identity.map_version, (5.0, 8.0), captured_at_ms=delayed_anchor)
    tracker.record_output(
        role_key, (1.0, 0.0), accepted_at_ms=delayed_anchor, ttl_ms=1_800,
    )
    page._follow_last_visual_positions[role_key] = (5.0, 8.0)
    page._follow_last_visual_at_ms[role_key] = delayed_anchor
    page._follow_last_evaluated_visual_at_ms[role_key] = delayed_anchor

    page._latest_dual_state = DualMotionState(
        "tracking", "visual", {"role-a": (25.0, 8.0), "role-b": (7.0, 10.0)}, transform,
    )
    page._latest_dual_captured_at_ms = now
    page._tick_follow_experiment()

    assert page._follow_rejected_visual == {}
    assert page._follow_last_visual_at_ms[role_key] == now
    assert page._follow_runtime is not None
    page.stop_follow_experiment()


def test_live_follow_cold_start_waits_for_post_arm_visual_before_output(tmp_path):
    page, outputs, transform = _dual_target_page(tmp_path)
    page.follow_p1_combo.setCurrentIndex(page.follow_p1_combo.findData("role-a"))
    page.follow_p2_combo.setCurrentIndex(page.follow_p2_combo.findData("role-b"))
    page.follow_mode_combo.setCurrentIndex(page.follow_mode_combo.findData("p1_leads"))
    initial = int(time.time() * 1000)
    page._latest_dual_state = DualMotionState(
        "tracking", "visual", {"role-a": (25.0, 8.0), "role-b": (5.0, 8.0)}, transform,
    )
    page._latest_dual_captured_at_ms = initial

    page.start_follow_experiment()

    # A runtime may be created from the accepted first frame, but the first
    # command must wait for a visual frame captured after the output lease was
    # armed.  The old implementation sent a full command in start_follow.
    assert outputs.get(2) is not None
    assert outputs[2].calls == []

    page._latest_dual_captured_at_ms = initial + 120
    page._latest_dual_state = DualMotionState(
        "tracking", "visual", {"role-a": (25.0, 8.0), "role-b": (5.0, 8.0)}, transform,
    )
    page._tick_follow_experiment()

    assert outputs[2].calls[0] == "start"
    assert any(call[0] == "write" for call in outputs[2].calls[1:])
    page.stop_follow_experiment()


def test_switching_between_move_probe_and_follow_releases_previous_mode(tmp_path):
    page, outputs, transform = _dual_target_page(tmp_path)
    page.program_probe_role_combo.setCurrentIndex(
        page.program_probe_role_combo.findData("role-a")
    )
    page.start_program_move_probe()
    assert page._program_probe_waiting_click

    page._latest_dual_state = DualMotionState(
        "tracking", "visual", {"role-a": (25.0, 5.0), "role-b": (5.0, 5.0)}, transform,
    )
    page._latest_dual_captured_at_ms = int(time.time() * 1000)
    page.follow_p1_combo.setCurrentIndex(page.follow_p1_combo.findData("role-a"))
    page.follow_p2_combo.setCurrentIndex(page.follow_p2_combo.findData("role-b"))
    page.follow_mode_combo.setCurrentIndex(page.follow_mode_combo.findData("p1_leads"))
    page.start_follow_experiment()
    assert not page._program_probe_waiting_click
    assert page._follow_runtime is not None
    _complete_live_follow_cold_start(page)
    assert outputs[2].calls[0] == "start"

    page.start_program_move_probe()
    assert page._follow_runtime is None
    assert outputs[2].calls[-1] == "stop"
    assert page._program_probe_waiting_click
    page.stop_program_move_probe()


def test_sidebar_tabs_keep_program_stop_available_from_log_view(tmp_path):
    page, outputs, _transform = _dual_target_page(tmp_path)
    assert [page.sidebar_tabs.tabText(index) for index in range(page.sidebar_tabs.count())] == [
        "采集定位", "移动跟随", "日志",
    ]
    assert not page.follow_footprint_radius.isEnabled()
    page.follow_mode_combo.setCurrentIndex(page.follow_mode_combo.findData("p1_leads"))
    assert page.follow_footprint_radius.isEnabled()
    page.start_dual_target_experiment()
    page._on_follow_map_click(25, 25)
    assert all(output.calls[0] == "start" for output in outputs.values())
    page._program_probe_recovery_target = (12.0, 12.0)
    page._dual_recovery_follow_live = True
    page._dual_target_recovery = ((25.0, 25.0), "role-a", "role-b", "example")

    page.sidebar_tabs.setCurrentIndex(2)
    page.stop_all_program_button.click()
    assert page._dual_target_runtime is None
    assert not page._dual_target_timer.isActive()
    assert all(output.calls[-1] == "stop" for output in outputs.values())
    assert page._dual_motion_tracker is not None
    assert page._program_probe_recovery_target is None
    assert page._dual_recovery_follow_live is False
    assert page._dual_target_recovery is None


def test_dual_target_experiment_waits_for_click_then_controls_both(tmp_path):
    page, outputs, _transform = _dual_target_page(tmp_path)

    page.start_dual_target_experiment()
    assert page._dual_target_runtime is not None
    assert not page._dual_target_timer.isActive()
    assert all(not output.calls for output in outputs.values())

    page._on_follow_map_click(20, 20)
    assert set(outputs) == {1, 2}
    assert all(output.calls[0] == "start" for output in outputs.values())
    assert all(any(call[0] == "write" for call in output.calls[1:]) for output in outputs.values())
    assert {
        observation.target_position for observation in page._dual_target_observations.values()
    } == {(20.0, 20.0)}
    assert len(page.map_widget.overlay_label._routes) == 2

    page._latest_dual_captured_at_ms = int(time.time() * 1000)
    page._on_follow_map_click(25, 25)
    assert {
        observation.target_position for observation in page._dual_target_observations.values()
    } == {(25.0, 25.0)}
    page.stop_dual_target_experiment()


def test_dual_target_start_is_idempotent_and_releases_previous_outputs(tmp_path):
    page, outputs, _transform = _dual_target_page(tmp_path)

    page.start_dual_target_experiment()
    page._on_follow_map_click(20, 20)
    first_outputs = dict(outputs)
    assert page._dual_target_runtime is not None

    page._latest_dual_captured_at_ms = int(time.time() * 1000)
    page.start_dual_target_experiment()

    assert first_outputs[1].calls[-1] == "stop"
    assert first_outputs[2].calls[-1] == "stop"
    assert page._dual_target_runtime is not None
    assert page._experiment_composition.dual_target_probe.armed
    page.stop_dual_target_experiment()


def test_dual_target_failed_bind_does_not_leave_probe_armed(tmp_path):
    page, _outputs, _transform = _dual_target_page(tmp_path)

    def fail_bind(_controller):
        raise RuntimeError("host unavailable")

    page.program_output_factory = fail_bind
    page.start_dual_target_experiment()

    assert page._dual_target_runtime is None
    assert page._dual_target_output is None
    assert not page._experiment_composition.dual_target_probe.armed


def test_dual_target_recovery_does_not_consume_frame_start_rejects(tmp_path, monkeypatch):
    page, outputs, transform = _dual_target_page(tmp_path)
    page.start_dual_target_experiment()
    page._on_follow_map_click(25, 25)
    page._save_dual_target_recovery_context()
    page.stop_dual_target_experiment(_preserve_recovery=True)

    page._latest_dual_state = DualMotionState(
        "tracking", "visual", {"role-a": (6.0, 6.0), "role-b": (9.0, 9.0)}, transform,
    )
    # The frame is fresh enough for the shared 700ms runtime/start gate, but
    # old enough to expose the former 1000ms recovery/start mismatch.
    monkeypatch.setattr(time, "time", lambda: 100.0)
    page._latest_dual_captured_at_ms = 99_500
    page._maybe_resume_dual_target_after_relocalization()

    assert page._dual_target_runtime is not None
    assert page._dual_target_recovery is None
    page.stop_dual_target_experiment()
    assert all(output.calls[-1] == "stop" for output in outputs.values())


def test_dual_target_experiment_releases_arrived_role_independently(tmp_path):
    page, outputs, transform = _dual_target_page(tmp_path)
    page.start_dual_target_experiment()
    page._latest_dual_captured_at_ms = int(time.time() * 1000)
    page._on_follow_map_click(25, 25)

    page._latest_dual_state = DualMotionState(
        "tracking", "visual", {"role-a": (25.0, 25.0), "role-b": (8.0, 8.0)}, transform,
    )
    page._latest_dual_captured_at_ms = int(time.time() * 1000)
    page._tick_dual_target_experiment()

    assert page._dual_target_observations["local-device:role-a"].state is FollowState.ARRIVED
    assert outputs[1].calls[-1] == "stop"
    assert outputs[2].calls[-1] != "stop"
    page.stop_dual_target_experiment()
    assert outputs[2].calls[-1] == "stop"


def test_dual_target_experiment_rejects_stale_visual_start(tmp_path):
    page, outputs, _transform = _dual_target_page(tmp_path)
    page._latest_dual_captured_at_ms = int(time.time() * 1000) - 2_000

    page.start_dual_target_experiment()

    assert page._dual_target_runtime is None
    assert outputs == {}
    assert "过期" in page.dual_target_status_label.text()


def test_dual_target_experiment_requires_real_visual_capture_timestamp(tmp_path):
    page, outputs, _transform = _dual_target_page(tmp_path)
    page._latest_dual_captured_at_ms = None

    page.start_dual_target_experiment()

    assert page._dual_target_runtime is None
    assert outputs == {}


def test_dual_target_experiment_pauses_on_stale_frame_and_resumes_on_fresh_frame(tmp_path):
    page, outputs, _transform = _dual_target_page(tmp_path)
    page.start_dual_target_experiment()
    page._latest_dual_captured_at_ms = int(time.time() * 1000)
    page._on_follow_map_click(25, 25)
    page._latest_dual_captured_at_ms = int(time.time() * 1000) - 2_000

    page._tick_dual_target_experiment()

    assert all(output.calls[-1] == "stop" for output in outputs.values())
    assert page._dual_target_runtime is not None
    page._latest_dual_captured_at_ms = int(time.time() * 1000)
    page._tick_dual_target_experiment()
    assert all(output.calls.count("start") == 2 for output in outputs.values())
    page.stop_dual_target_experiment()


def test_dual_target_experiment_releases_both_when_visual_recovery_begins(tmp_path):
    page, outputs, transform = _dual_target_page(tmp_path)
    page.start_dual_target_experiment()
    page._on_follow_map_click(25, 25)
    page._latest_dual_state = DualMotionState(
        "recovering", "lost", {"role-a": None, "role-b": None}, transform,
        recovery_requested=True,
    )

    page._tick_dual_target_experiment()

    assert all(output.calls[-1] == "stop" for output in outputs.values())
    assert page._dual_target_runtime is not None
    page.stop_dual_target_experiment()


def test_dual_target_experiment_replays_target_after_fresh_relocalization(tmp_path):
    page, outputs, transform = _dual_target_page(tmp_path)
    page.start_dual_target_experiment()
    page._on_follow_map_click(25, 25)
    page._save_dual_target_recovery_context()
    page.stop_dual_target_experiment(_preserve_recovery=True)
    assert all(output.calls[-1] == "stop" for output in outputs.values())

    page._latest_dual_captured_at_ms = int(time.time() * 1000)
    page._latest_dual_state = DualMotionState(
        "tracking", "visual", {"role-a": (5.0, 5.0), "role-b": (8.0, 8.0)}, transform,
    )
    page._maybe_resume_dual_target_after_relocalization()

    assert page._dual_target_recovery is None
    assert page._dual_target_runtime is not None
    page._latest_dual_captured_at_ms = int(time.time() * 1000)
    page._on_follow_map_click(25, 25)
    assert len(page._dual_target_observations) == 2
    assert all(outputs[controller].calls[0] == "start" for controller in (1, 2))
    page.stop_dual_target_experiment()


def test_dual_target_experiment_rearms_arrived_role_on_new_click(tmp_path):
    page, outputs, transform = _dual_target_page(tmp_path)
    page.start_dual_target_experiment()
    page._latest_dual_captured_at_ms = int(time.time() * 1000)
    page._on_follow_map_click(20, 20)
    page._latest_dual_state = DualMotionState(
        "tracking", "visual", {"role-a": (20.0, 20.0), "role-b": (8.0, 8.0)}, transform,
    )
    page._tick_dual_target_experiment()
    assert outputs[1].calls[-1] == "stop"

    # The product intentionally rejects frames older than 700 ms.  Refresh
    # the synthetic capture timestamp before the second click so a slow full
    # test run does not turn this re-arm contract into a timing flake.
    page._latest_dual_captured_at_ms = int(time.time() * 1000)
    page._on_follow_map_click(30, 30)

    assert outputs[1].calls.count("start") == 2
    assert outputs[2].calls.count("start") == 1
    page.stop_dual_target_experiment()


def test_dual_target_experiment_stops_when_follow_starts(tmp_path):
    page, outputs, _transform = _dual_target_page(tmp_path)
    page.start_dual_target_experiment()
    page._on_follow_map_click(20, 20)
    page.follow_p1_combo.setCurrentIndex(page.follow_p1_combo.findData("role-a"))
    page.follow_p2_combo.setCurrentIndex(page.follow_p2_combo.findData("role-b"))
    page.follow_mode_combo.setCurrentIndex(page.follow_mode_combo.findData("both"))

    page.start_follow_experiment()

    assert page._dual_target_runtime is None
    assert all(output.calls[-1] == "stop" for output in outputs.values())
    assert page._follow_runtime is not None
    page.stop_follow_experiment()


def test_dual_target_experiment_releases_both_on_output_error(tmp_path):
    page, outputs, _transform = _dual_target_page(tmp_path)
    page.start_dual_target_experiment()
    outputs[2].write = lambda _vector, *, elapsed_ms: (_ for _ in ()).throw(RuntimeError("host failed"))

    page._on_follow_map_click(20, 20)

    assert page._dual_target_runtime is None
    assert outputs[1].calls[-1] == "stop"
    assert outputs[2].calls[-1] == "stop"
    assert "输出失败" in page.dual_target_status_label.text() or "目标执行失败" in page.dual_target_status_label.text()


def test_dual_target_experiment_stops_both_on_runtime_failure(tmp_path):
    page, outputs, _transform = _dual_target_page(tmp_path)
    page.start_dual_target_experiment()
    page._on_follow_map_click(20, 20)
    runtime = page._dual_target_runtime
    assert runtime is not None
    runtime.tick = lambda **_kwargs: (_ for _ in ()).throw(RuntimeError("planner failed"))
    page._latest_dual_captured_at_ms = int(time.time() * 1000)

    page._tick_dual_target_experiment()

    assert page._dual_target_runtime is None
    assert all(output.calls[-1] == "stop" for output in outputs.values())
    assert "失败" in page.dual_target_status_label.text()


def test_dual_target_experiment_releases_only_stale_role(tmp_path):
    page, outputs, transform = _dual_target_page(tmp_path)
    page.start_dual_target_experiment()
    page._latest_dual_captured_at_ms = int(time.time() * 1000)
    page._on_follow_map_click(25, 25)
    role_a = page._dual_target_roles[0]
    runtime = page._dual_target_runtime
    assert runtime is not None
    runtime.update_follower_position(
        PositionSample(
            role_a, runtime.map_identity, (5.0, 5.0),
            int(time.time() * 1000) - 2_000, 1.0, "visual",
        )
    )
    page._latest_dual_state = DualMotionState(
        "tracking", "one_missing", {"role-a": None, "role-b": (8.0, 8.0)}, transform,
    )
    page._latest_dual_captured_at_ms = int(time.time() * 1000)

    page._tick_dual_target_experiment()

    # A stale native sample is held as bounded command prediction; the target
    # controller remains armed until a newer position arrives.
    assert page._dual_target_observations[role_a.key].state is FollowState.PROGRAM_READY
    assert page._dual_target_observations[role_a.key].vector != (0.0, 0.0)
    assert outputs[1].calls[-1][0] == "write"
    assert outputs[1].calls[-1][1] != (0.0, 0.0)
    assert outputs[2].calls[-1] != "stop"
    page.stop_dual_target_experiment()


def test_dual_target_experiment_stops_timer_when_both_arrive(tmp_path):
    page, outputs, transform = _dual_target_page(tmp_path)
    page.start_dual_target_experiment()
    page._on_follow_map_click(25, 25)
    page._latest_dual_state = DualMotionState(
        "tracking", "visual", {"role-a": (25.0, 25.0), "role-b": (25.0, 25.0)}, transform,
    )
    page._latest_dual_captured_at_ms = int(time.time() * 1000)

    page._tick_dual_target_experiment()

    assert not page._dual_target_timer.isActive()
    assert all(output.calls[-1] == "stop" for output in outputs.values())
    page.stop_dual_target_experiment()


def test_dual_target_experiment_feeds_local_contact_for_both_roles(tmp_path):
    page, _outputs, transform = _dual_target_page(tmp_path)
    page.start_dual_target_experiment()
    page._on_follow_map_click(25, 25)
    contacts = []
    runtime = page._dual_target_runtime
    assert runtime is not None
    runtime.update_local_contact = lambda role, **data: contacts.append((role, data))
    page._latest_dual_combined = np.zeros((32, 32), dtype=np.uint8)
    page._latest_dual_state = SimpleNamespace(
        status="tracking", reason="visual", wall_quality=1.0, recovery_requested=False,
        players={"role-a": (5.0, 5.0), "role-b": (8.0, 8.0)},
        screen_positions={"role-a": (5.0, 5.0), "role-b": (8.0, 8.0)},
        transform=transform,
    )
    page._latest_dual_captured_at_ms = int(time.time() * 1000)

    page._tick_dual_target_experiment()

    assert {role.actor_id for role, _data in contacts} == {"role-a", "role-b"}
    page.stop_dual_target_experiment()


def test_dual_target_experiment_requests_one_global_relocalization(tmp_path):
    page, outputs, _transform = _dual_target_page(tmp_path)
    page.start_dual_target_experiment()
    page._on_follow_map_click(25, 25)
    role = page._dual_target_roles[0]
    relocalizations = []
    page._start_dual_motion = lambda *, recovery: relocalizations.append(recovery)
    runtime = page._dual_target_runtime
    assert runtime is not None
    runtime.tick = lambda **_kwargs: {
        role.key: FollowObservation(
            FollowState.BLOCKED, role, RoleId("remote-device", "target"),
            position=(5.0, 5.0), target_position=(25.0, 25.0),
            reason="contact_relocalization_required",
            diagnostics={"relocalization_requested": True},
        )
    }

    page._tick_dual_target_experiment()

    assert relocalizations == [True]
    assert all(output.calls[-1] == "stop" for output in outputs.values())
    assert page._dual_target_recovery is not None
    page.stop_dual_target_experiment()


def test_dual_target_experiment_ignores_out_of_bounds_click(tmp_path):
    page, _outputs, _transform = _dual_target_page(tmp_path)
    page.start_dual_target_experiment()
    page._on_follow_map_click(25, 25)
    previous = page._clicked_target_display

    page._on_follow_map_click(40, 40)

    assert page._clicked_target_display == previous
    runtime = page._dual_target_runtime
    assert runtime is not None
    position = runtime.remote.position
    assert position is not None
    assert position.position == (25.0, 25.0)
    assert "仍前往上一目标" in page.dual_target_status_label.text()
    page.stop_dual_target_experiment()


def test_dual_target_overlay_does_not_invent_route_when_planner_has_no_path(tmp_path):
    page, _outputs, _transform = _dual_target_page(tmp_path)
    page.start_dual_target_experiment()
    page._on_follow_map_click(25, 25)
    role = page._dual_target_roles[0]
    page._dual_target_observations = {
        role.key: FollowObservation(
            FollowState.BLOCKED, role, RoleId("remote-device", "target"),
            position=(5.0, 5.0), target_position=(25.0, 25.0), route=(),
            reason="no_path",
        )
    }

    page._render_dual_target_overlay()

    assert not page.map_widget.overlay_label._routes
    assert page.map_widget.overlay_label._target == (25.0, 25.0)
    page.stop_dual_target_experiment()


def test_dual_target_click_round_trip_matches_real_rotated_reflected_run():
    transform = SimilarityTransform2D(
        221.0, True, 0.874, (387.411582048845, 863.1283120739718),
    )
    source_size = (2784, 2093)
    display_click = (1039.0, 2099.0)

    native_point = localization_source_point(
        display_click, source_size=source_size, transform=transform,
    )
    round_trip = localization_display_point(
        native_point, source_size=source_size, transform=transform,
    )

    assert abs(native_point[0] - 606.168047104487) < 1e-6
    assert abs(native_point[1] - 1204.9081494381662) < 1e-6
    assert max(abs(a - b) for a, b in zip(round_trip, display_click)) < 1e-6


def test_dual_target_experiment_stops_after_sequential_arrivals(tmp_path):
    page, outputs, transform = _dual_target_page(tmp_path)
    page.start_dual_target_experiment()
    page._on_follow_map_click(25, 25)

    page._latest_dual_state = DualMotionState(
        "tracking", "visual", {"role-a": (25.0, 25.0), "role-b": (8.0, 8.0)}, transform,
    )
    page._latest_dual_captured_at_ms = int(time.time() * 1000)
    page._tick_dual_target_experiment()
    assert outputs[1].calls[-1] == "stop"
    assert outputs[2].calls[-1] != "stop"
    assert page._dual_target_timer.isActive()

    page._latest_dual_state = DualMotionState(
        "tracking", "visual", {"role-a": (25.0, 25.0), "role-b": (25.0, 25.0)}, transform,
    )
    page._latest_dual_captured_at_ms = int(time.time() * 1000)
    page._tick_dual_target_experiment()

    assert not page._dual_target_timer.isActive()
    assert outputs[1].calls[-1] == "stop"
    assert outputs[2].calls[-1] == "stop"
    page.stop_dual_target_experiment()
