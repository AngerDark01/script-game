from __future__ import annotations

import time

import cv2
import numpy as np

from auto_modules.features.poe2.live_terrain.experimental.follow_engine.contracts import VisualObservation
from auto_modules.features.poe2.live_terrain.experimental.follow_engine.composition import (
    FollowSeedBundle,
    SpawnSafeFollowRuntimeFactory,
    build_follow_engine_composition,
)
from auto_modules.features.poe2.live_terrain.experimental.follow_engine.contracts import ObservationSource
from auto_modules.features.poe2.live_terrain.experimental.hybrid_localization.models import SimilarityTransform2D
from auto_modules.features.poe2.live_terrain.experimental.follow_engine.control.route_controller import MapAwareRouteController
from auto_modules.features.poe2.live_terrain.experimental.follow_engine.generation import GenerationClock
from auto_modules.features.poe2.live_terrain.experimental.follow_engine.vision.capture_adapter import EncodedImageCapture


class StaticImageProvider:
    def __init__(self):
        self.image = np.zeros((100, 100, 3), dtype=np.uint8)
        cv2.circle(self.image, (30, 40), 3, (0, 0, 255), -1)
        cv2.circle(self.image, (70, 60), 3, (0, 255, 255), -1)

    def __call__(self):
        return self.image


class RecordingOutput:
    def __init__(self):
        self.started = 0
        self.snapshots = []
        self.stopped = 0

    def start(self):
        self.started += 1

    def apply(self, snapshot):
        self.snapshots.append(snapshot)

    def stop(self, *, force=True):
        self.stopped += 1


class MemorySource:
    def read_many(self, expected_instance_id):
        return (
            type("Sample", (), {"identity": "p1", "grid": (1, 2), "area_instance": expected_instance_id})(),
            type("Sample", (), {"identity": "p2", "grid": (3, 4), "area_instance": expected_instance_id})(),
        )


def translate(point):
    return (point[0] + 10.0, point[1] + 20.0)


def make_memory_source():
    return MemorySource()


def test_offline_composition_runs_seeded_vision_ring_control_and_output():
    output = RecordingOutput()
    capture = EncodedImageCapture(
        StaticImageProvider(), generation=1, map_instance="map-a", image_format=".png"
    )
    composition = build_follow_engine_composition(
        seed=FollowSeedBundle(
            map_instance="map-a",
            roles={"p1": 1, "p2": 2},
            initial_positions_native={"p1": (30, 40), "p2": (70, 60)},
        ),
        capture=capture,
        output=output,
        interval_ms=10,
        ring_capacity=2,
        ring_slot_size=64 * 1024,
        route_controller=MapAwareRouteController(np.zeros((100, 100), dtype=np.uint8)),
        memory_source=MemorySource(),
        memory_transform=translate,
    )
    composition.start()
    try:
        deadline = time.monotonic() + 5.0
        snapshot = None
        while time.monotonic() < deadline and snapshot is None:
            candidate = composition.port.poll()
            if candidate is not None and set(candidate.roles) == {"p1", "p2"}:
                snapshot = candidate
            time.sleep(0.01)
        assert snapshot is not None
        assert snapshot.session_active is True
        assert output.started == 1
        assert output.snapshots
        assert composition.port.diagnostics()["worker_state"] == {"vision": "running", "control": "running"}
    finally:
        composition.stop()
    assert output.stopped == 1


def test_seed_bundle_rejects_role_position_mismatch():
    try:
        FollowSeedBundle(
            map_instance="map-a",
            roles={"p1": 1, "p2": 2},
            initial_positions_native={"p1": (1, 2)},
        )
    except ValueError as exc:
        assert "match roles" in str(exc)
    else:
        raise AssertionError("invalid seed bundle was accepted")


def test_spawn_safe_factory_wires_warm_memory_and_map_route_without_side_effects():
    wall_map = np.zeros((80, 80), dtype=np.uint8)
    wall_map[38:42, 8:72] = 255
    route = MapAwareRouteController(wall_map, arrival_radius=3.0, lookahead_points=1)
    token = GenerationClock().begin("map-a")
    runtime = SpawnSafeFollowRuntimeFactory(
        route_controller=route,
        memory_source=MemorySource(),
        memory_transform=translate,
        expected_players=2,
    )(token, {"p1": 1, "p2": 2})
    try:
        assert runtime.memory_recovery is not None
        assert runtime.route_controller is route
        runtime.seed_position("p1", (10.0, 10.0), captured_at_ms=1)
        runtime.update_target("p1", (70.0, 70.0))
        snapshot = runtime.tick(now_ms=100)
        assert snapshot.output_intents[0].neutral is False
        assert snapshot.route
    finally:
        runtime.close()


def test_map_route_replans_only_after_target_or_corridor_threshold():
    wall_map = np.zeros((80, 80), dtype=np.uint8)
    controller = MapAwareRouteController(
        wall_map,
        arrival_radius=3.0,
        target_refresh_distance=10.0,
        route_replan_distance=20.0,
    )
    first = controller.plan((10.0, 10.0), (70.0, 70.0))
    second = controller.plan((11.0, 11.0), (70.0, 70.0))
    assert first.vector != (0.0, 0.0)
    assert second.vector != (0.0, 0.0)
    assert controller.replan_count == 1
    controller.plan((11.0, 11.0), (70.0, 30.0))
    assert controller.replan_count == 2


def test_factory_can_construct_reader_inside_child_and_rejects_map_mismatch():
    token = GenerationClock().begin("map-a")
    runtime = SpawnSafeFollowRuntimeFactory(
        memory_source_factory=make_memory_source,
        memory_transform=translate,
        expected_players=2,
    )(token, {"p1": 1, "p2": 2})
    try:
        assert runtime.memory_recovery is not None
    finally:
        runtime.close()
    mismatched = MapAwareRouteController(np.zeros((20, 20), dtype=np.uint8), map_instance="map-b")
    try:
        build_follow_engine_composition(
            seed=FollowSeedBundle(
                map_instance="map-a",
                roles={"p1": 1},
                initial_positions_native={"p1": (2, 2)},
            ),
            capture=EncodedImageCapture(StaticImageProvider(), generation=1, map_instance="map-a"),
            output=RecordingOutput(),
            route_controller=mismatched,
        )
    except ValueError as exc:
        assert "map instance" in str(exc)
    else:
        raise AssertionError("mismatched route map was accepted")


def test_rebuild_handover_falls_back_to_seed_transform_for_legacy_observation():
    transform = SimilarityTransform2D(12.0, False, 1.25, (9.0, 11.0))
    composition = build_follow_engine_composition(
        seed=FollowSeedBundle(
            map_instance="map-a",
            roles={"p1": 1, "p2": 2},
            initial_positions_native={"p1": (30, 40), "p2": (70, 60)},
            transform=transform,
        ),
        capture=EncodedImageCapture(StaticImageProvider(), generation=1, map_instance="map-a"),
        output=RecordingOutput(),
    )
    composition.port._last_visual_observation = VisualObservation(
        generation=1,
        sequence=1,
        captured_at_ms=33,
        map_instance="map-a",
        roles={},
        source=ObservationSource.NONE,
    )
    bundle = composition.port._rebuild_factory()
    try:
        assert bundle.vision.processor.transform == transform
        assert bundle.control.runtime_factory.local_search.transform == transform
    finally:
        bundle.close()
        composition.stop(reason="test")
