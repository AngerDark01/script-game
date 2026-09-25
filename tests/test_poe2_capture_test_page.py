from __future__ import annotations

import os
from pathlib import Path
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import numpy as np
from PySide6.QtWidgets import QApplication

from auto_modules.core.mapping import MapStitcher
from auto_modules.features.poe2.live_terrain.contracts import (
    CaptureMetadata,
    TerrainSessionState,
    TerrainSnapshot,
)
from auto_modules.features.poe2.live_terrain.capture_samples import CaptureSampleArchive
from auto_modules.features.poe2.live_terrain.player_position import PlayerPositionSample
from auto_modules.features.poe2.live_terrain.stitching_archive import Poe2StitchingArchive
from auto_modules.features.poe2.live_terrain.stitching_session import Poe2StitchingSession
from auto_modules.features.poe2.live_terrain.experimental.hybrid_localization.models import (
    HybridLocalizationMode,
    HybridLocalizationState,
)
from auto_modules.ui.modes.poe2_live_terrain.capture_test_page import Poe2CaptureTestPage


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
    def preprocess_image(self, frame):
        return frame + 1

    def extract_combined(self, frame, player_pos=None):
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
