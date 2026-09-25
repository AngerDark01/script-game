from __future__ import annotations

import os
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import numpy as np
from PySide6.QtWidgets import QApplication

from auto_modules.features.poe2.live_terrain.contracts import CaptureMetadata, TerrainSessionState, TerrainSnapshot
from auto_modules.features.poe2.live_terrain.experimental.multiframe_localization.models import PositionEstimate
from auto_modules.ui.modes.poe2_live_terrain.capture_test_page import Poe2CaptureTestPage


def _snapshot():
    metadata = CaptureMetadata("Area", "hash", "Area:hash", 8, 8, "2026-09-23T00:00:00+00:00")
    return TerrainSnapshot(
        metadata,
        np.zeros((8, 8), dtype=np.uint8),
        np.ones((8, 8), dtype=np.int8),
        np.full((8, 8), 255, dtype=np.uint8),
        np.zeros((8, 8), dtype=np.uint8),
        np.full((8, 8), 255, dtype=np.uint8),
    )


class Service:
    def __init__(self):
        self.state = TerrainSessionState.NEW
        self.value = _snapshot()

    def initialize(self):
        self.state = TerrainSessionState.READY_TO_CAPTURE

    def capture(self):
        self.state = TerrainSessionState.CAPTURED
        return self.value

    def snapshot(self):
        return self.value if self.state is TerrainSessionState.CAPTURED else None

    def reset(self):
        self.state = TerrainSessionState.NEW


class Session:
    def __init__(self, estimate):
        self.estimate = estimate
        self.active = False
        self.registration_pending = False
        self.closed = False

    def start(self):
        self.active = True

    def tick(self):
        return self.estimate

    def close(self):
        self.closed = True
        self.active = False


class Factory:
    def __init__(self):
        estimate = PositionEstimate("confirmed", (3, 4), (0, 0), np.eye(2), (), "Area:hash", 1, 2, True, 0, "test", "ok")
        self.session = Session(estimate)
        self.coordinator = SimpleNamespace(
            recovery_revision=0,
            registration=None,
            phase=SimpleNamespace(value="tracking"),
            last_strategy_a_result=SimpleNamespace(status="confirmed"),
            last_strategy_b_result=None,
            set_strategies_enabled=lambda **kwargs: setattr(self, "selected", kwargs),
        )
        self.window = SimpleNamespace(snapshot=lambda: ())
        self.submap = SimpleNamespace(rebuild=lambda frames: SimpleNamespace(wall_mask=np.eye(8, dtype=np.uint8) * 255))
        self.anchor_provider = SimpleNamespace(read_count=1)
        self.archive = SimpleNamespace(save=lambda *args, **kwargs: None)

    def __call__(self, snapshot, config_provider):
        del snapshot, config_provider
        return SimpleNamespace(
            session=self.session,
            coordinator=self.coordinator,
            window=self.window,
            submap=self.submap,
            anchor_provider=self.anchor_provider,
            archive=self.archive,
        )


def test_multiframe_controls_publish_one_shared_state_and_stop_cleanly():
    QApplication.instance() or QApplication([])
    factory = Factory()
    page = Poe2CaptureTestPage(
        Service(),
        archive=SimpleNamespace(save=lambda snapshot: None),
        monitor_config=SimpleNamespace(sample_interval_ms=100, binding=SimpleNamespace()),
        preview_provider=lambda config: np.zeros((8, 8, 3), dtype=np.uint8),
        multiframe_localization_factory=factory,
    )
    page.initialize_session()
    page.capture_map()
    assert page.start_multiframe_button.isEnabled()

    page.start_preview()
    assert page.preview_timer.isActive()

    page.multiframe_panel.strategy_b_check.setChecked(False)
    page.start_multiframe_localization()

    assert factory.selected == {"strategy_a": True, "strategy_b": False}
    assert not page.multiframe_panel.save_button.isEnabled()
    assert "关键帧 0" in page.multiframe_panel.diagnostics_label.text()
    assert "(3.0, 4.0)" in page.multiframe_position_label.text()
    assert not page.multiframe_panel.submap_preview.pixmap().isNull()
    page.stop_multiframe_localization()
    assert factory.session.closed
    assert not page._multiframe_timer.isActive()
    assert not page.preview_timer.isActive()
    assert page._multiframe_experiment is None


def test_multiframe_start_rejects_missing_monitor_binding_before_factory_call():
    QApplication.instance() or QApplication([])
    factory = Factory()
    page = Poe2CaptureTestPage(
        Service(),
        archive=SimpleNamespace(save=lambda snapshot: None),
        monitor_config=SimpleNamespace(sample_interval_ms=100, binding=None),
        preview_provider=lambda config: np.zeros((8, 8, 3), dtype=np.uint8),
        multiframe_localization_factory=factory,
    )
    page.initialize_session()
    page.capture_map()

    page.start_multiframe_localization()

    assert factory.session.active is False
    assert "小地图监控区域" in page.error_label.text()
