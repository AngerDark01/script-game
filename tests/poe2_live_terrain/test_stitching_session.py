from __future__ import annotations

from datetime import datetime, timezone

import numpy as np

from auto_modules.core.mapping import MapStitcher
from auto_modules.features.poe2.live_terrain.capture_samples import CaptureEvidence
from auto_modules.features.poe2.live_terrain.stitching_session import Poe2StitchingSession


class FakeStitcher:
    def __init__(self) -> None:
        self.draw_scale = 2.0
        self.canvas_size = 1000
        self.wall_close_kernel_size = 3
        self.params = {}
        self.received = []
        self.position = (100, 100)
        self.stats = {
            "total_frames": 0,
            "successful_matches": 0,
            "failed_matches": 0,
            "match_quality": 0.0,
            "match_rate": 0.0,
            "keyframe_switches": 0,
            "low_quality_skipped": 0,
        }

    def add_evidence(self, evidence) -> bool:
        self.received.append(evidence)
        self.stats["total_frames"] += 1
        if self.stats["total_frames"] > 1:
            self.stats["successful_matches"] += 1
            self.stats["match_quality"] = 0.8
            self.position = (self.position[0] + 4, self.position[1] - 2)
        return True

    def get_enhanced_map(self, margin=500):
        return np.full((12, 16, 3), 60, dtype=np.uint8), (92, 88)

    def get_current_position(self):
        return self.position

    def get_statistics(self):
        return dict(self.stats)

    def set_params(self, params):
        self.params.update(params)
        self.draw_scale = float(params.get("draw_scale", self.draw_scale))
        self.canvas_size = int(params.get("canvas_size", self.canvas_size))
        self.wall_close_kernel_size = int(
            params.get("wall_close_kernel_size", self.wall_close_kernel_size)
        )


def _evidence(value: int = 1) -> CaptureEvidence:
    raw = np.full((8, 10, 3), value, dtype=np.uint8)
    feature = np.full((8, 10), 127, dtype=np.uint8)
    wall = np.zeros((8, 10), dtype=np.uint8)
    wall[2:6, 3:7] = 255
    fog = np.zeros((8, 10), dtype=np.uint8)
    fog[1:7, 2:8] = 255
    return CaptureEvidence(
        captured_at=datetime.now(timezone.utc).isoformat(),
        raw=raw,
        processed=np.full((8, 10), value + 1, dtype=np.uint8),
        feature=feature,
        monitor_config={"binding": {"player_marker_position": [4, 3]}},
        wall_mask=wall,
        fog_mask=fog,
        raw_gray=np.full((8, 10), value + 2, dtype=np.uint8),
    )


def test_session_lifecycle_does_not_consume_while_idle_or_paused():
    created = []

    def factory():
        stitcher = FakeStitcher()
        created.append(stitcher)
        return stitcher

    session = Poe2StitchingSession(stitcher_factory=factory)
    stitcher = created[0]

    assert session.snapshot().state == "idle"
    assert session.consume(_evidence()).statistics["total_frames"] == 0
    assert stitcher.received == []

    assert session.start().state == "running"
    first = session.consume(_evidence())
    assert first.statistics["total_frames"] == 1
    assert first.trajectory == ((100, 100),)

    assert session.pause().state == "paused"
    paused = session.consume(_evidence(2))
    assert paused.statistics["total_frames"] == 1
    assert len(stitcher.received) == 1

    reset = session.reset()
    assert reset.state == "idle"
    assert reset.trajectory == ()
    assert reset.statistics["total_frames"] == 0
    assert len(created) == 2


def test_session_passes_distinct_mapping_layers_and_tracks_accepted_positions():
    stitcher = FakeStitcher()
    session = Poe2StitchingSession(stitcher_factory=lambda: stitcher)
    session.start()

    first = session.consume(_evidence())
    second = session.consume(_evidence(2))

    mapped = stitcher.received[-1]
    assert np.array_equal(mapped.match_mask, np.full((8, 10), 127, dtype=np.uint8))
    assert np.count_nonzero(mapped.save_mask) == 16
    assert np.count_nonzero(mapped.fog_mask) == 36
    assert mapped.player_position == (4.0, 3.0)
    assert int(mapped.raw_gray[0, 0]) == 4
    assert first.map_origin == (92, 88)
    assert first.map_image is not None and first.map_image.shape == (12, 16, 3)
    assert second.current_position == (104, 98)
    assert second.trajectory == ((100, 100), (104, 98))


def test_session_falls_back_to_center_and_stable_layers_when_optional_masks_are_absent():
    stitcher = FakeStitcher()
    session = Poe2StitchingSession(stitcher_factory=lambda: stitcher)
    evidence = CaptureEvidence(
        captured_at=datetime.now(timezone.utc).isoformat(),
        raw=np.ones((6, 8, 3), dtype=np.uint8),
        processed=np.ones((6, 8, 3), dtype=np.uint8),
        feature=np.full((6, 8), 255, dtype=np.uint8),
        monitor_config={},
    )

    session.start()
    session.consume(evidence)

    mapped = stitcher.received[0]
    assert mapped.player_position == (4.0, 3.0)
    assert np.array_equal(mapped.save_mask, evidence.feature)
    assert np.count_nonzero(mapped.fog_mask) == 0
    assert mapped.raw_gray.shape == (6, 8)


def test_session_places_first_frame_through_real_map_stitcher():
    session = Poe2StitchingSession(
        stitcher_factory=lambda: MapStitcher(canvas_size=100, draw_scale=1.0)
    )

    session.start()
    snapshot = session.consume(_evidence())

    assert snapshot.current_position == (50, 50)
    assert snapshot.trajectory == ((50, 50),)
    assert snapshot.map_image is not None
    assert np.count_nonzero(snapshot.map_image) > 0
    assert snapshot.statistics["total_frames"] == 1


def test_session_applies_stitcher_params_and_reset_preserves_them():
    created = []

    def factory():
        stitcher = FakeStitcher()
        created.append(stitcher)
        return stitcher

    params = {
        "canvas_size": 4200,
        "draw_scale": 1.5,
        "wall_close_kernel_size": 5,
        "weight_add": 0.45,
    }
    session = Poe2StitchingSession(stitcher_params=params, stitcher_factory=factory)

    assert created[0].canvas_size == 4200
    assert created[0].draw_scale == 1.5
    assert created[0].wall_close_kernel_size == 5
    assert created[0].params["weight_add"] == 0.45

    session.reset()

    assert len(created) == 2
    assert created[1].params["weight_add"] == 0.45
    assert created[1].draw_scale == 1.5


def test_session_configure_is_stable_for_same_params_and_rebuilds_when_idle():
    created = []

    def factory():
        stitcher = FakeStitcher()
        created.append(stitcher)
        return stitcher

    session = Poe2StitchingSession(
        stitcher_params={"canvas_size": 3000, "draw_scale": 2.0},
        stitcher_factory=factory,
    )

    session.configure({"canvas_size": 3000, "draw_scale": 2.0})
    assert len(created) == 1

    session.configure({"canvas_size": 5000, "draw_scale": 2.0, "weight_add": 0.4})
    assert len(created) == 2
    assert created[1].canvas_size == 5000
    assert created[1].params["weight_add"] == 0.4
    assert session.snapshot().state == "idle"


def test_session_rejects_parameter_changes_while_running():
    session = Poe2StitchingSession(stitcher_factory=FakeStitcher)
    session.start()

    import pytest

    with pytest.raises(RuntimeError, match="暂停"):
        session.configure({"canvas_size": 5100})
