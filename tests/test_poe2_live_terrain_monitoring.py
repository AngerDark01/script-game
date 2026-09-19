import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import numpy as np
from PySide6.QtWidgets import QApplication

from auto_modules.features.poe2.live_terrain.contracts import (
    CaptureMetadata,
    TerrainSessionState,
    TerrainSnapshot,
)
from auto_modules.features.poe2.live_terrain.monitor_config import Poe2MonitorConfigStore
from auto_modules.core.spatial.monitor_binding import CaptureRect, MonitorBinding
from auto_modules.ui.modes.poe2_live_terrain.page import Poe2LiveTerrainPage
from auto_modules.core.localization import LocalizationResult, ObservationCandidate
from auto_modules.features.poe2.live_terrain.runtime import Poe2LocalizationState


def _snapshot():
    metadata = CaptureMetadata("A", "h", "A:h", 4, 4, "2026-09-19T00:00:00+00:00")
    return TerrainSnapshot(
        metadata,
        np.zeros((4, 4), dtype=np.uint8),
        np.ones((4, 4), dtype=np.int8),
        np.ones((4, 4), dtype=np.uint8),
        np.zeros((4, 4), dtype=np.uint8),
        np.ones((4, 4), dtype=np.uint8),
    )


class Service:
    state = TerrainSessionState.CAPTURED

    def snapshot(self):
        return _snapshot()

    def reset(self):
        self.state = TerrainSessionState.NEW


class Runtime:
    def __init__(self):
        self.started = False
        self.stopped = False

    def start(self):
        self.started = True

    def stop(self):
        self.stopped = True

    def tick(self, *, now_ms=None):
        return Poe2LocalizationState(
            raw_frame=np.zeros((8, 8, 3), dtype=np.uint8),
            selected_candidate=ObservationCandidate((3, 4), 0.9),
            localization=LocalizationResult((2.0, 1.0), 0.9, source="global"),
            latest_confirmed_position=(2.0, 1.0),
            trajectory=((2.0, 1.0),),
            mode="local_tracking",
            source="global",
            confidence=0.9,
        )


def test_page_monitoring_updates_preview_and_stops_timer(tmp_path):
    app = QApplication.instance() or QApplication([])
    store = Poe2MonitorConfigStore(tmp_path)
    config = store.load()
    store.save(config.__class__(binding=MonitorBinding(CaptureRect(0, 0, 8, 8))))
    runtime = Runtime()
    page = Poe2LiveTerrainPage(service=Service(), runtime=runtime, config_store=store)
    page.capture_map()
    page.start_monitoring()
    assert runtime.started is True
    assert page.monitor_timer.isActive() is True
    page._tick_runtime()
    assert not page.minimap_preview.pixmap().isNull()
    assert "global" in page.localization_status.text()
    page.stop_monitoring()
    assert runtime.stopped is True
    assert page.monitor_timer.isActive() is False
    page.deleteLater()
