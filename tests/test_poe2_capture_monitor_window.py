from __future__ import annotations

import os
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import numpy as np
import pytest
from PySide6.QtWidgets import QApplication

from auto_modules.features.poe2.live_terrain.capture_samples import CaptureSampleArchive
from auto_modules.features.poe2.live_terrain.contracts import CaptureMetadata, TerrainSnapshot
from auto_modules.features.poe2.live_terrain.player_position import PlayerPositionSample
from auto_modules.features.poe2.live_terrain.stitching_session import Poe2StitchingSnapshot
from auto_modules.features.poe2.live_terrain.experimental.hybrid_localization.models import (
    HybridLocalizationMode,
    HybridLocalizationState,
)
from auto_modules.ui.modes.poe2_live_terrain.capture_monitor_window import (
    Poe2CaptureMonitorWindow,
)


def _app():
    return QApplication.instance() or QApplication([])


def _terrain() -> TerrainSnapshot:
    metadata = CaptureMetadata("Area", "hash", "Area:hash", 3, 2, "2026-09-21T00:00:00+00:00")
    return TerrainSnapshot(
        metadata,
        np.zeros((2, 3), dtype=np.uint8),
        np.ones((2, 3), dtype=np.int8),
        np.full((2, 3), 255, dtype=np.uint8),
        np.zeros((2, 3), dtype=np.uint8),
        np.full((2, 3), 255, dtype=np.uint8),
    )


class FakeRecognizer:
    def preprocess_image(self, frame):
        return frame + 1

    def extract_combined(self, frame, player_pos=None):
        feature = np.full(frame.shape[:2], int(frame[0, 0, 0]) + 2, dtype=np.uint8)
        wall = np.full(frame.shape[:2], int(frame[0, 0, 0]) + 3, dtype=np.uint8)
        fog = np.full(frame.shape[:2], int(frame[0, 0, 0]) + 4, dtype=np.uint8)
        return feature, wall, fog

    def get_raw_gray(self, frame):
        return np.full(frame.shape[:2], int(frame[0, 0, 0]) + 5, dtype=np.uint8)


class FakeStitchingSession:
    def __init__(self):
        self.state = "idle"
        self.consumed = []
        self.reset_calls = 0
        self.configured = []

    def configure(self, params):
        self.configured.append(dict(params))
        return self.snapshot()

    def start(self):
        self.state = "running"
        return self.snapshot()

    def pause(self):
        if self.state == "running":
            self.state = "paused"
        return self.snapshot()

    def reset(self):
        self.state = "idle"
        self.consumed.clear()
        self.reset_calls += 1
        return self.snapshot()

    def consume(self, evidence):
        self.consumed.append(evidence)
        return self.snapshot()

    def snapshot(self):
        has_frame = bool(self.consumed)
        return Poe2StitchingSnapshot(
            state=self.state,
            map_image=np.full((12, 16, 3), 60, dtype=np.uint8),
            map_origin=(90, 88),
            current_position=(100, 100) if has_frame else None,
            trajectory=((100, 100),) if has_frame else (),
            statistics={
                "total_frames": len(self.consumed),
                "successful_matches": max(0, len(self.consumed) - 1),
                "failed_matches": 0,
                "match_quality": 0.8 if has_frame else 0.0,
                "match_rate": 100.0 if has_frame else 0.0,
                "keyframe_switches": 0,
                "low_quality_skipped": 0,
            },
            draw_scale=2.0,
            player_position=(4.0, 3.0) if has_frame else None,
            capture_size=(8, 6) if has_frame else None,
        )


class FakeStitchingArchive:
    def __init__(self, root):
        self.root = root
        self.saved = []

    def save(self, snapshot, evidence, *, terrain=None):
        self.saved.append((snapshot, evidence, terrain))
        return self.root / "saved-session"


def _config():
    return SimpleNamespace(
        sample_interval_ms=50,
        binding=SimpleNamespace(player_marker_position=(4, 3)),
        as_dict=lambda: {
            "profile_id": "test",
            "binding": {"player_marker_position": [4, 3]},
            "map_rotation": 0,
            "map_flip_horizontal": False,
            "map_flip_vertical": False,
            "stitcher_params": {"canvas_size": 5000, "weight_add": 0.4},
        },
        stitcher_params={"canvas_size": 5000, "weight_add": 0.4},
    )


def test_monitor_refresh_builds_one_synchronized_evidence_frame(tmp_path):
    _app()
    calls = []

    def provider(config):
        calls.append(config)
        return np.full((6, 8, 3), 7, dtype=np.uint8)

    window = Poe2CaptureMonitorWindow(
        preview_provider=provider,
        recognizer=FakeRecognizer(),
        monitor_config_provider=_config,
        terrain_snapshot_provider=_terrain,
        sample_archive=CaptureSampleArchive(tmp_path / "samples"),
        stitching_session=FakeStitchingSession(),
        stitching_archive=FakeStitchingArchive(tmp_path / "stitching"),
    )
    window.refresh_frame()

    assert len(calls) == 1
    assert window.current_evidence is not None
    assert int(window.current_evidence.raw[0, 0, 0]) == 7
    assert int(window.current_evidence.processed[0, 0, 0]) == 8
    assert int(window.current_evidence.feature[0, 0]) == 9
    assert not window.wall_preview.pixmap().isNull()
    assert window.save_button.isEnabled()
    assert not window.terrain_preview.pixmap().isNull()


def test_monitor_previews_resize_with_window_and_panels_are_draggable(tmp_path):
    app = _app()
    window = Poe2CaptureMonitorWindow(
        preview_provider=lambda config: np.full((80, 80, 3), 7, dtype=np.uint8),
        recognizer=FakeRecognizer(),
        monitor_config_provider=_config,
        terrain_snapshot_provider=_terrain,
        sample_archive=CaptureSampleArchive(tmp_path / "samples"),
        stitching_session=FakeStitchingSession(),
        stitching_archive=FakeStitchingArchive(tmp_path / "stitching"),
    )
    window.resize(1500, 920)
    window.show()
    app.processEvents()
    window.refresh_frame()
    before = window.raw_preview.pixmap().size()
    window.resize(1900, 1100)
    app.processEvents()
    assert window.raw_preview.pixmap().width() > before.width()
    assert window.workspace_splitter.count() == 2
    assert window.content_splitter.count() == 2
    window.close()


def test_saved_sample_includes_initial_memory_position(tmp_path):
    _app()
    position = PlayerPositionSample.from_world(
        world=(10.0, 20.0, -3.0),
        captured_at="2026-09-21T00:00:01+00:00",
        area_instance="Area:hash",
    )
    window = Poe2CaptureMonitorWindow(
        preview_provider=lambda _config: np.full((6, 8, 3), 7, dtype=np.uint8),
        recognizer=FakeRecognizer(),
        monitor_config_provider=_config,
        terrain_snapshot_provider=_terrain,
        sample_archive=CaptureSampleArchive(tmp_path / "samples"),
        stitching_session=FakeStitchingSession(),
        stitching_archive=FakeStitchingArchive(tmp_path / "stitching"),
        player_position_provider=lambda: position,
    )

    window.refresh_frame()
    record = window.save_current_sample()

    assert record is not None
    assert record.manifest["player_position"]["area_instance"] == "Area:hash"
    assert record.manifest["player_position"]["grid"] == pytest.approx([0.92, 1.84])


def test_monitor_failure_invalidates_old_frame_and_close_stops_timer(tmp_path):
    _app()
    fail = False

    def provider(_config):
        if fail:
            raise RuntimeError("game closed")
        return np.full((6, 8, 3), 7, dtype=np.uint8)

    window = Poe2CaptureMonitorWindow(
        preview_provider=provider,
        recognizer=FakeRecognizer(),
        monitor_config_provider=_config,
        terrain_snapshot_provider=_terrain,
        sample_archive=CaptureSampleArchive(tmp_path / "samples"),
        stitching_session=FakeStitchingSession(),
        stitching_archive=FakeStitchingArchive(tmp_path / "stitching"),
    )
    window.start_monitoring()
    assert window.preview_timer.isActive()
    assert window.current_evidence is not None
    fail = True
    window.refresh_frame()

    assert window.current_evidence is None
    assert not window.save_button.isEnabled()
    assert window.raw_preview.pixmap().isNull()
    assert window.wall_preview.pixmap().isNull()
    assert "game closed" in window.error_label.text()
    window.close()
    assert not window.preview_timer.isActive()
    assert window.current_evidence is None


def test_saved_samples_are_available_for_previous_next_comparison(tmp_path):
    _app()
    value = 1

    def provider(_config):
        return np.full((6, 8, 3), value, dtype=np.uint8)

    window = Poe2CaptureMonitorWindow(
        preview_provider=provider,
        recognizer=FakeRecognizer(),
        monitor_config_provider=_config,
        terrain_snapshot_provider=_terrain,
        sample_archive=CaptureSampleArchive(tmp_path / "samples"),
        stitching_session=FakeStitchingSession(),
        stitching_archive=FakeStitchingArchive(tmp_path / "stitching"),
    )
    window.refresh_frame()
    first = window.save_current_sample()
    value = 5
    window.refresh_frame()
    second = window.save_current_sample()

    assert first is not None and second is not None
    assert len(window.history_records) == 2
    assert window.history_index == 1
    assert not window.history_current_preview.pixmap().isNull()
    assert not window.history_previous_preview.pixmap().isNull()
    window.show_previous_sample()
    assert window.history_index == 0
    assert "没有更早样本" in window.history_previous_preview.text()
    window.show_next_sample()
    assert window.history_index == 1


def test_stitching_controls_reuse_current_evidence_and_archive_result(tmp_path):
    _app()
    calls = []
    session = FakeStitchingSession()
    archive = FakeStitchingArchive(tmp_path / "stitching")

    def provider(config):
        calls.append(config)
        return np.full((6, 8, 3), 7, dtype=np.uint8)

    window = Poe2CaptureMonitorWindow(
        preview_provider=provider,
        recognizer=FakeRecognizer(),
        monitor_config_provider=_config,
        terrain_snapshot_provider=_terrain,
        sample_archive=CaptureSampleArchive(tmp_path / "samples"),
        stitching_session=session,
        stitching_archive=archive,
    )

    window.start_stitching()

    assert session.configured == [{"canvas_size": 5000, "weight_add": 0.4}]
    assert len(calls) == 1
    assert len(session.consumed) == 1
    evidence = session.consumed[0]
    assert int(evidence.feature[0, 0]) == 9
    assert int(evidence.wall_mask[0, 0]) == 10
    assert int(evidence.fog_mask[0, 0]) == 11
    assert int(evidence.raw_gray[0, 0]) == 12
    assert not window.start_stitching_button.isEnabled()
    assert window.pause_stitching_button.isEnabled()
    assert window.save_stitching_button.isEnabled()
    assert window.stitching_map.original_pixmap is not None
    assert not window.stitching_map.original_pixmap.isNull()
    assert "匹配率 100.0%" in window.stitching_status_label.text()

    path = window.save_stitching_session()
    assert path == archive.root / "saved-session"
    assert archive.saved[0][1] is window.current_evidence
    assert archive.saved[0][2] is window._current_terrain

    window.reset_stitching()
    assert session.reset_calls == 1
    assert not window.save_stitching_button.isEnabled()
    window.close()


def test_monitor_window_mirrors_hybrid_state_on_terrain_preview(tmp_path):
    _app()
    window = Poe2CaptureMonitorWindow(
        preview_provider=lambda _config: np.full((6, 8, 3), 7, dtype=np.uint8),
        recognizer=FakeRecognizer(),
        monitor_config_provider=_config,
        terrain_snapshot_provider=_terrain,
        sample_archive=CaptureSampleArchive(tmp_path / "samples"),
        stitching_session=FakeStitchingSession(),
        stitching_archive=FakeStitchingArchive(tmp_path / "stitching"),
    )
    window.refresh_frame()
    state = HybridLocalizationState(
        mode=HybridLocalizationMode.LOCAL_TRACKING,
        position=(1.0, 1.0),
        latest_confirmed_position=(1.0, 1.0),
        trajectory=((0.0, 0.0), (1.0, 1.0)),
        registration=None,
        source="visual_local",
        confidence=0.8,
        reason="",
        recovery_revision=2,
    )

    window.handle_hybrid_state(state, read_count=2)

    assert "visual_local" in window.hybrid_status_label.text()
    assert "读取 2 次" in window.hybrid_status_label.text()
    assert not window.terrain_preview.pixmap().isNull()
