import os
import threading
import time
from types import SimpleNamespace

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
        self.configured = []
        self.retries = 0

    def configure_monitor(self, config):
        self.configured.append(config)

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

    def retry_recovery(self):
        self.retries += 1


def test_page_monitoring_updates_preview_and_stops_timer(tmp_path):
    app = QApplication.instance() or QApplication([])
    store = Poe2MonitorConfigStore(tmp_path)
    config = store.load()
    store.save(config.__class__(binding=MonitorBinding(CaptureRect(0, 0, 8, 8))))
    runtime = Runtime()
    page = Poe2LiveTerrainPage(service=Service(), runtime=runtime, config_store=store)
    assert runtime.configured == [page.monitor_config]
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


def test_background_monitor_does_not_block_and_discards_stopped_result(tmp_path):
    app = QApplication.instance() or QApplication([])
    store = Poe2MonitorConfigStore(tmp_path)
    store.save(store.load().__class__(binding=MonitorBinding(CaptureRect(0, 0, 8, 8))))

    class SlowRuntime(Runtime):
        run_in_background = True

        def __init__(self):
            super().__init__()
            self.entered = threading.Event()
            self.release = threading.Event()

        def tick(self, *, now_ms=None):
            self.entered.set()
            self.release.wait(2.0)
            return super().tick(now_ms=now_ms)

    runtime = SlowRuntime()
    page = Poe2LiveTerrainPage(service=Service(), runtime=runtime, config_store=store)
    started = time.perf_counter()
    page.start_monitoring()
    assert time.perf_counter() - started < 0.2
    assert runtime.entered.wait(1.0)
    page.stop_monitoring()
    runtime.release.set()
    deadline = time.perf_counter() + 2.0
    while page._localization_worker is not None and time.perf_counter() < deadline:
        app.processEvents()
        time.sleep(0.01)
    assert page._localization_worker is None
    assert runtime.stopped is True
    assert page.localization_status.text() == "定位：未启动"
    page.deleteLater()


def test_page_retains_localization_worker_when_bounded_stop_times_out(tmp_path):
    app = QApplication.instance() or QApplication([])
    store = Poe2MonitorConfigStore(tmp_path)
    store.save(store.load().__class__(binding=MonitorBinding(CaptureRect(0, 0, 8, 8))))
    page = Poe2LiveTerrainPage(service=Service(), runtime=Runtime(), config_store=store)

    class SlowWorker:
        generation = 7
        is_running = True

        def stop(self):
            return None

        def wait(self, timeout_ms):
            assert timeout_ms == 3000
            return False

    worker = SlowWorker()
    page._localization_worker = worker
    page.stop_monitoring()

    assert page._localization_worker is None
    assert page._retired_localization_workers == [worker]
    page._on_worker_finished(worker.generation, worker)
    assert page._retired_localization_workers == []
    page.deleteLater()


def test_page_pauses_terminal_recovery_and_retry_restarts_timer(tmp_path):
    app = QApplication.instance() or QApplication([])
    store = Poe2MonitorConfigStore(tmp_path)
    config = store.load()
    store.save(config.__class__(binding=MonitorBinding(CaptureRect(0, 0, 8, 8))))
    runtime = Runtime()
    page = Poe2LiveTerrainPage(service=Service(), runtime=runtime, config_store=store)
    page.start_monitoring()
    state = SimpleNamespace(
        raw_frame=np.zeros((8, 8, 3), dtype=np.uint8),
        processed_frame=np.ones((8, 8, 3), dtype=np.uint8),
        match_mask=np.full((8, 8), 255, dtype=np.uint8),
        position=None,
        latest_confirmed_position=(2.0, 1.0),
        trajectory=((2.0, 1.0),),
        local_position=(4.0, 4.0),
        mode=SimpleNamespace(value="recovery_required"),
        source="failed",
        confidence=0.0,
        reason="absolute_registration_failed",
        recovery_revision=2,
        memory_read_count=2,
        diagnostics={"reason": "anchor_outside_search_window"},
        frame_elapsed_ms=5.0,
    )

    page.handle_runtime_state(state)

    status = page.localization_status.text()
    assert "recovery_required" in status
    assert "恢复版本：2" in status
    assert "内存读取：2" in status
    assert "需要重新定位" in status
    assert page.monitor_timer.isActive() is False
    assert page.retry_localization_button.isEnabled() is True

    page.retry_localization()

    assert runtime.retries == 1
    assert page.monitor_timer.isActive() is True
    assert page.retry_localization_button.isEnabled() is False
    page.stop_monitoring()
    page.deleteLater()


def test_match_preview_keeps_successful_frame_visible(tmp_path):
    app = QApplication.instance() or QApplication([])
    store = Poe2MonitorConfigStore(tmp_path)
    store.save(store.load().__class__(binding=MonitorBinding(CaptureRect(0, 0, 8, 8))))
    page = Poe2LiveTerrainPage(service=Service(), runtime=Runtime(), config_store=store)

    state = SimpleNamespace(
        raw_frame=np.zeros((8, 8, 3), dtype=np.uint8),
        processed_frame=np.ones((8, 8, 3), dtype=np.uint8),
        match_mask=np.full((8, 8), 255, dtype=np.uint8),
        position=None,
        latest_confirmed_position=None,
        trajectory=(),
        local_position=None,
        mode=SimpleNamespace(value="local_tracking"),
        source="visual",
        confidence=0.8,
        reason="",
        recovery_revision=0,
        memory_read_count=0,
        diagnostics={},
        frame_elapsed_ms=1.0,
    )

    page._update_frame_previews(state)

    assert not page.match_preview.pixmap().isNull()
    assert page.match_preview.text() == ""
    page.deleteLater()
