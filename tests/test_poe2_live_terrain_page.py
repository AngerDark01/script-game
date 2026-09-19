import os

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
