"""Offline contracts for scrolling frames and recovered dynamic targets."""

from dataclasses import replace

import cv2
import numpy as np
import pytest

from auto_modules.features.poe2.live_terrain.experimental.follow_engine.contracts import RoleVisualObservation, VisualObservation
from auto_modules.features.poe2.live_terrain.experimental.follow_engine.control.follow_control_process import FollowControlRuntime
from auto_modules.features.poe2.live_terrain.experimental.follow_engine.generation import GenerationClock
from auto_modules.features.poe2.live_terrain.experimental.follow_engine.recovery.local_recovery import LocalRecoveryBackend
from auto_modules.features.poe2.live_terrain.experimental.follow_engine.shared_frame_ring import SharedFrameRecord, SharedFrameRing
from auto_modules.features.poe2.live_terrain.experimental.follow_engine.vision.capture_adapter import CapturedFrame
from auto_modules.features.poe2.live_terrain.experimental.follow_engine.vision.local_roi_search import EncodedMarkerRoiSearch
from auto_modules.features.poe2.live_terrain.experimental.hybrid_localization.models import SimilarityTransform2D
from auto_modules.features.poe2.live_terrain.experimental.hybrid_localization.similarity_search import transform_local_point


def test_scrolled_frame_local_recovery_uses_that_frames_transform():
    old = SimilarityTransform2D(0, False, 1, (0, 0))
    current = replace(old, translation=(100, 30))
    image = np.zeros((100, 100, 3), dtype=np.uint8)
    cv2.circle(image, (30, 40), 3, (0, 0, 255), -1)
    ok, encoded = cv2.imencode(".png", image)
    assert ok
    native = transform_local_point(image.shape[:2], (30, 40), angle=0,
                                   reflect_horizontal=False, scale=1, translation=current.translation)
    runtime = FollowControlRuntime(GenerationClock().begin("map-a"), {"p2": 2},
                                   local_recovery=LocalRecoveryBackend(),
                                   local_search=EncodedMarkerRoiSearch(transform=old))
    runtime.seed_position("p2", native, captured_at_ms=0)
    runtime.apply_visual(VisualObservation(1, 1, 33, "map-a", {
        "p2": RoleVisualObservation("p2", None, visible=False),
    }, transform=current), frame=CapturedFrame(1, 1, 33, "map-a", encoded.tobytes()))
    result = runtime.tick(now_ms=33)
    assert result.roles["p2"].source == "local_roi"
    assert result.roles["p2"].position_native == pytest.approx(native, abs=1)


def test_overwritten_frame_does_not_pair_new_image_with_old_transform():
    ring = SharedFrameRing(capacity=2, slot_size=128, map_instance="map-a")
    try:
        runtime = FollowControlRuntime(GenerationClock().begin("map-a"), {"p2": 2}, frame_ring=ring)
        runtime.seed_position("p2", (10, 20), captured_at_ms=0)
        runtime.update_target("p2", (100, 20))
        for sequence in (2, 3, 4):
            ring.publish(SharedFrameRecord(1, sequence, sequence * 33, "map-a", b"image"))
        observation = VisualObservation(1, 2, 66, "map-a", {
            "p2": RoleVisualObservation("p2", None, visible=False),
        }, transform=SimilarityTransform2D(0, False, 1, (0, 0)))
        runtime.apply_visual(observation)
        assert runtime._latest_frame is None
        result = runtime.tick(now_ms=132)
        assert result.session_active
        assert not result.output_intents[0].neutral
    finally:
        ring.close(unlink=True)


def test_stale_observation_cannot_rebind_roi_and_explicit_frame_must_match():
    transform = SimilarityTransform2D(0, False, 1, (100, 30))
    search = EncodedMarkerRoiSearch()
    runtime = FollowControlRuntime(GenerationClock().begin("map-a"), {"p2": 2}, local_search=search)
    observation = VisualObservation(1, 2, 66, "map-a", {
        "p2": RoleVisualObservation("p2", None, visible=False),
    }, transform=transform)
    assert runtime.apply_visual(observation, frame=CapturedFrame(1, 3, 99, "map-a", b"other-frame"))
    assert runtime._latest_frame is None
    assert search.transform == transform
    assert not runtime.apply_visual(replace(observation, sequence=1, transform=replace(transform, translation=(0, 0))))
    assert search.transform == transform


@pytest.mark.parametrize("source", ["local_roi", "memory_reanchor", "global_reanchor"])
@pytest.mark.parametrize("leader,follower", [("p1", "p2"), ("p2", "p1")])
def test_recovered_leader_updates_dynamic_target(source, leader, follower):
    runtime = FollowControlRuntime(GenerationClock().begin("map-a"), {follower: 1},
                                   observation_role_ids=("p1", "p2"),
                                   live_target_source=leader, live_target_roles=(follower,),
                                   live_target_initial_position=(0, 0))
    runtime.seed_position(leader, (0, 0), captured_at_ms=0)
    runtime.seed_position(follower, (-20, 0), captured_at_ms=0)
    assert runtime._apply_recovery_positions({leader: (100, 20)}, now_ms=100, source=source)
    assert runtime._roles[follower].target == (100, 20)
    runtime._apply_recovery_positions({follower: (90, 20)}, now_ms=110, source=source)
    assert runtime._roles[follower].target == (100, 20)
