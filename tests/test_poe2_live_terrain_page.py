import os
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import numpy as np
from PySide6.QtWidgets import QApplication

from auto_modules.ui.modes.poe2_live_terrain.page import Poe2LiveTerrainPage
from auto_modules.features.poe2.live_terrain.contracts import CaptureMetadata, TerrainSnapshot, TerrainSessionState


def _snapshot():
    metadata = CaptureMetadata("Area", "hash", "Area:hash", 1, 1, "2026-09-19T00:00:00+00:00")
    return TerrainSnapshot(
        metadata,
        np.zeros((1, 1), dtype=np.uint8),
        np.ones((1, 1), dtype=np.int8),
        np.full((1, 1), 255, dtype=np.uint8),
        np.zeros((1, 1), dtype=np.uint8),
        np.full((1, 1), 255, dtype=np.uint8),
    )


class FakeService:
    def __init__(self, error=None):
        self.state = TerrainSessionState.NEW
        self.error = error
        self.snapshot_value = _snapshot()

    def initialize(self):
        if self.error:
            raise self.error
        self.state = TerrainSessionState.READY_TO_CAPTURE

    def capture(self):
        if self.error:
            raise self.error
        self.state = TerrainSessionState.CAPTURED
        return self.snapshot_value

    def reset(self):
        self.state = TerrainSessionState.NEW

    def snapshot(self):
        return self.snapshot_value if self.state is TerrainSessionState.CAPTURED else None


def test_page_controls_and_successful_capture_are_service_driven():
    app = QApplication.instance() or QApplication([])
    service = FakeService()
    page = Poe2LiveTerrainPage(service)
    assert page.capture_button.isEnabled() is False
    page.initialize_session()
    assert page.capture_button.isEnabled() is True
    page.capture_map()
    assert page.map_widget.original_pixmap.size().width() == 1
    assert "Area:hash" in page.metadata_label.text()
    page.reset_session()
    assert page.map_widget.original_pixmap is None


def test_page_clears_map_on_capture_error():
    app = QApplication.instance() or QApplication([])
    service = FakeService()
    page = Poe2LiveTerrainPage(service)
    page.initialize_session()
    page.capture_map()
    service.error = RuntimeError("no process")
    service.state = TerrainSessionState.READY_TO_CAPTURE
    page.capture_map()
    assert page.map_widget.original_pixmap is None
    assert "no process" in page.error_label.text()


def test_page_displays_processed_frame_and_actual_match_mask():
    app = QApplication.instance() or QApplication([])
    page = Poe2LiveTerrainPage(FakeService())
    state = SimpleNamespace(
        processed_frame=np.ones((8, 8, 3), dtype=np.uint8),
        raw_frame=np.zeros((8, 8, 3), dtype=np.uint8),
        match_mask=np.full((8, 8), 255, dtype=np.uint8),
        source="global",
        confidence=0.9,
        position=(10.0, 20.0),
        local_position=(4, 4),
        failure_reason="",
        mode="track_local",
        frame_elapsed_ms=1.0,
        recognition_diagnostics={},
    )

    page.handle_runtime_state(state)

    assert page.minimap_preview.pixmap() is not None
    assert page.match_preview.pixmap() is not None

    empty_state = SimpleNamespace(
        processed_frame=None,
        raw_frame=None,
        match_mask=None,
        source="failed",
        confidence=0.0,
        position=None,
        local_position=None,
        failure_reason="capture_failed",
        mode="need_global",
        frame_elapsed_ms=1.0,
        recognition_diagnostics={},
    )
    page.handle_runtime_state(empty_state)
    assert page.minimap_preview.pixmap().isNull()
    assert page.match_preview.pixmap().isNull()


def test_page_exposes_capture_test_tab_with_isolated_service(tmp_path):
    app = QApplication.instance() or QApplication([])
    live_service = FakeService()
    test_service = FakeService()

    class Archive:
        def save(self, snapshot):
            return tmp_path / "latest.npz"

    page = Poe2LiveTerrainPage(
        live_service,
        capture_test_service=test_service,
        capture_test_archive=Archive(),
        capture_preview=lambda _config: np.zeros((8, 8, 3), dtype=np.uint8),
        capture_recognizer=None,
    )

    assert page.tabs.count() == 2
    assert page.tabs.tabText(0) == "实时地形定位"
    assert page.tabs.tabText(1) == "数据采集测试"
    page.capture_test_page.initialize_session()
    page.capture_test_page.capture_map()

    assert live_service.snapshot() is None
    assert test_service.snapshot() is not None


def test_embedded_capture_tab_receives_hybrid_experiment_factory(tmp_path):
    app = QApplication.instance() or QApplication([])

    class Archive:
        def save(self, snapshot):
            return tmp_path / "latest.npz"

    page = Poe2LiveTerrainPage(
        FakeService(),
        capture_test_service=FakeService(),
        capture_test_archive=Archive(),
        hybrid_localization_factory=lambda snapshot, config_provider: object(),
    )

    assert page.capture_test_page.hybrid_localization_factory is not None
    assert page.capture_test_page.hybrid_timer.isActive() is False
    page.deleteLater()


def test_monitor_dialog_uses_composed_preview_and_recognizer_dependencies():
    app = QApplication.instance() or QApplication([])
    preview = lambda config: np.zeros((8, 8, 3), dtype=np.uint8)
    recognizer = SimpleNamespace(get_params=lambda: {"edge_low": 31})
    page = Poe2LiveTerrainPage(
        FakeService(),
        capture_preview=preview,
        capture_recognizer=recognizer,
    )

    page.open_monitor_config()

    assert page.monitor_dialog.preview_provider is preview
    assert page.monitor_dialog.recognizer_params_provider is recognizer.get_params
    page.monitor_dialog.close()
    page.deleteLater()


def test_unchanged_position_does_not_rebuild_registered_map(monkeypatch):
    app = QApplication.instance() or QApplication([])
    service = FakeService()
    page = Poe2LiveTerrainPage(service)
    page.initialize_session()
    page.capture_map()
    calls = []

    def prepare_map(base, transform=None):
        calls.append((base, state))
        return base

    monkeypatch.setattr(
        "auto_modules.ui.modes.poe2_live_terrain.page.prepare_localization_map",
        prepare_map,
    )
    state = SimpleNamespace(
        processed_frame=None,
        raw_frame=None,
        match_mask=None,
        source="visual_local",
        confidence=0.8,
        position=(10.0, 20.0),
        latest_confirmed_position=(10.0, 20.0),
        trajectory=((10.0, 20.0),),
        local_position=(4.0, 4.0),
        reason="",
        mode="local_tracking",
        recovery_revision=1,
        memory_read_count=1,
        frame_elapsed_ms=4.0,
        diagnostics={},
    )

    page.handle_runtime_state(state)
    page.handle_runtime_state(state)

    assert len(calls) == 1
    page.deleteLater()
