from __future__ import annotations

import multiprocessing as mp
import time
from types import SimpleNamespace

import numpy as np

from auto_modules.features.poe2.live_terrain.experimental.hybrid_localization.models import SimilarityTransform2D
from auto_modules.features.poe2.live_terrain.experimental.multiplayer_localization.models import PlayerLocalization, PlayerMarkerCandidate
from auto_modules.core.spatial.capture_geometry import CaptureShape
from auto_modules.core.spatial.monitor_binding import CaptureRect, MonitorBinding
from auto_modules.features.poe2.live_terrain.experimental.follow_engine.engine import FollowEngineStart
from auto_modules.ui.modes.poe2_live_terrain.follow_engine_page_composition import (
    build_poe2_follow_engine_page_adapter,
    build_follow_seed_from_dual_result,
)


class _SpawnBackend:
    def __init__(self):
        self.image = np.zeros((120, 120, 3), dtype=np.uint8)
        import cv2
        cv2.rectangle(self.image, (8, 8), (108, 108), (255, 255, 255), 2)
        cv2.circle(self.image, (30, 40), 3, (0, 0, 255), -1)
        cv2.circle(self.image, (82, 72), 3, (0, 255, 255), -1)

    def capture(self, _left, _top, width, height):
        return self.image[:height, :width].copy()

    def close(self):
        return None


def _spawn_backend_factory():
    return _SpawnBackend()


class _SpawnOutput:
    def __init__(self, controller):
        self.controller = int(controller)
        self.started = 0
        self.writes = []
        self.stopped = 0

    def start(self):
        self.started += 1

    def write(self, vector, *, elapsed_ms):
        self.writes.append((tuple(vector), int(elapsed_ms)))

    def heartbeat(self):
        return True

    def rearm(self):
        return None

    def stop(self):
        self.stopped += 1

    def close(self):
        self.stop()

    def snapshot(self):
        return {"controller": self.controller, "writes": len(self.writes)}


def _spawn_output_factory(controller):
    return _SpawnOutput(controller)


def test_seed_builder_preserves_first_frame_identity_keys_and_all_observation_roles():
    transform = SimilarityTransform2D(219.0, False, 0.75, (10.0, 20.0))
    result = SimpleNamespace(
        accepted=True,
        primary_registration=SimpleNamespace(transform=transform),
        players={
            "DexFourb": PlayerLocalization(
                "DexFourb", "c1", (30.0, 40.0), (100.0, 200.0), (101.0, 201.0), 1.0, 0.9, True
            ),
            "StrDexFourb": PlayerLocalization(
                "StrDexFourb", "c2", (80.0, 60.0), (140.0, 220.0), (141.0, 221.0), 1.2, 0.88, True
            ),
        },
    )
    seed = build_follow_seed_from_dual_result(
        map_instance="map-a",
        result=result,
        roles={"StrDexFourb": 2},
    )
    assert seed.observation_role_ids == ("DexFourb", "StrDexFourb")
    assert seed.roles == {"StrDexFourb": 2}
    assert seed.initial_positions_native["DexFourb"] == (101.0, 201.0)
    assert seed.transform == transform


def test_seed_builder_carries_distinct_first_frame_identity_hints():
    transform = SimilarityTransform2D(0.0, False, 1.0, (0.0, 0.0))
    result = SimpleNamespace(
        accepted=True,
        primary_registration=SimpleNamespace(transform=transform),
        players={
            "p1": PlayerLocalization("p1", "c1", (10.0, 10.0), (10.0, 10.0), (10.0, 10.0), 0.0, 1.0, True),
            "p2": PlayerLocalization("p2", "c2", (20.0, 20.0), (20.0, 20.0), (20.0, 20.0), 0.0, 1.0, True),
        },
    )
    candidates = (
        PlayerMarkerCandidate("c1", (10.0, 10.0), color_features={"identity_hint": "blue"}),
        PlayerMarkerCandidate("c2", (20.0, 20.0), color_features={"identity_hint": "orange"}),
    )
    seed = build_follow_seed_from_dual_result(
        map_instance="map-a", result=result, roles={"p1": 1, "p2": 2}, initial_candidates=candidates
    )
    assert dict(seed.identity_hints) == {"p1": "blue", "p2": "orange"}


def test_concrete_page_composition_runs_spawned_capture_control_and_live_target_refresh():
    from auto_modules.features.poe2.live_terrain.experimental.follow_engine.composition import FollowSeedBundle

    seed = FollowSeedBundle(
        map_instance="map-a",
        roles={"p2": 2},
        observation_role_ids=("p1", "p2"),
        initial_positions_native={"p1": (30.0, 40.0), "p2": (82.0, 72.0)},
        initial_screen_positions={"p1": (30.0, 40.0), "p2": (82.0, 72.0)},
        transform=SimilarityTransform2D(0.0, False, 1.0, (0.0, 0.0)),
    )
    monitor_config = SimpleNamespace(
        binding=MonitorBinding(CaptureRect(0, 0, 120, 120)),
        shape=CaptureShape.SQUARE,
        circle_radius=None,
        recognizer_params={},
        localization_fps=30,
    )
    adapter, composition = build_poe2_follow_engine_page_adapter(
        seed=seed,
        monitor_config=monitor_config,
        program_output_factory=_spawn_output_factory,
        wall_map=np.zeros((120, 120), dtype=np.uint8),
        leader_role="p1",
        target_roles=("p2",),
        arm_delay_ms=0,
        capture_backend_factory=_spawn_backend_factory,
    )
    adapter.start(FollowEngineStart("map-a", {"p2": 2}))
    try:
        deadline = time.monotonic() + 8.0
        state = None
        while time.monotonic() < deadline:
            state = adapter.poll()
            if state.snapshot is not None and set(state.snapshot.roles) == {"p1", "p2"}:
                break
            time.sleep(0.01)
        assert state is not None and state.snapshot is not None
        assert set(state.snapshot.roles) == {"p1", "p2"}
        assert state.snapshot.output_intents
    finally:
        adapter.stop(reason="test")
        composition.stop(reason="test")
