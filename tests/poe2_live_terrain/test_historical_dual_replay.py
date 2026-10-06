from __future__ import annotations

import time
from pathlib import Path
from types import SimpleNamespace

import cv2
import numpy as np

from auto_modules.core.localization import LocalizationResult
from auto_modules.features.poe2.live_terrain.experimental.hybrid_localization.models import (
    AbsoluteRegistration,
    HybridFrame,
    PositionAnchor,
    SimilarityTransform2D,
)
from auto_modules.features.poe2.live_terrain.experimental.multiplayer_localization.dual_first_frame import (
    DualFirstFrameRegistrar,
)
from auto_modules.features.poe2.live_terrain.experimental.multiplayer_localization.dual_motion import (
    DualVisualTracker,
)
from auto_modules.features.poe2.live_terrain.experimental.multiplayer_localization.marker_candidates import (
    detect_saturated_marker_observation,
    marker_candidates_from_observation,
)
from auto_modules.features.poe2.live_terrain.experimental.multiplayer_localization.models import (
    DualFirstFrameResult,
    MarkerColorProfile,
    PlayerLocalization,
)
from auto_modules.ui.modes.poe2_live_terrain.dual_motion_worker import (
    Poe2DualMotionWorker,
)


ROOT = Path(__file__).resolve().parents[2]
SAMPLE = ROOT / "data" / "poe2_live_terrain_test" / "samples" / "dual_player_20260925"
INSTANCE = "MapFlotsam:73681455"


def _profiles() -> tuple[MarkerColorProfile, ...]:
    # These are the calibrated orange/blue profiles used by the archived
    # dual-player capture.  The test intentionally reuses the real image; it
    # does not synthesize marker pixels or write application logs.
    return (
        MarkerColorProfile("orange", 5, 25, 130, 80, 8.0, 55.0, 14),
        MarkerColorProfile("blue", 85, 125, 100, 70, 8.0, 55.0, 14),
    )


def _load_sample() -> tuple[np.ndarray, np.ndarray]:
    raw = cv2.imread(str(SAMPLE / "raw.png"), cv2.IMREAD_COLOR)
    wall = cv2.imread(str(SAMPLE / "wall.png"), cv2.IMREAD_GRAYSCALE)
    assert raw is not None and wall is not None
    assert raw.shape[:2] == wall.shape == (300, 300)
    return raw, wall


def _historical_candidates(raw: np.ndarray):
    observation = detect_saturated_marker_observation(
        raw,
        1,
        profiles=_profiles(),
    )
    return observation, marker_candidates_from_observation(observation, max_candidates=4)


def _fixture_first_frame(wall: np.ndarray, candidates) -> DualFirstFrameResult:
    # The archived raw and dual memory probe have different coordinate extents:
    # the probe has native anchors, while the matching terrain reference is not
    # present in this repository.  For an offline geometry replay, place those
    # anchors at the observed marker coordinates.  This keeps the registration
    # problem deterministic and explicitly avoids mixing map instances.
    anchor_positions = {"p1": (86.0, 148.0), "p2": (75.0, 155.0)}
    reference = SimpleNamespace(
        walkable_mask=wall == 0,
        wall_layer=wall,
        explored_map=np.full(wall.shape, 255, dtype=np.uint8),
        width=wall.shape[1],
        height=wall.shape[0],
        metadata={"instance_id": "offline-fixture"},
        shape=wall.shape,
    )
    # TerrainReference performs the immutable/shape validation required by the
    # registrar while keeping the fixture local to this test.
    from auto_modules.features.poe2.live_terrain.terrain_reference import TerrainReference

    typed_reference = TerrainReference(
        walkable_mask=reference.walkable_mask,
        wall_layer=reference.wall_layer,
        explored_map=reference.explored_map,
        width=reference.width,
        height=reference.height,
        metadata=reference.metadata,
    )
    anchors = {
        identity: PositionAnchor(position, "offline-fixture", 1, "historical-image")
        for identity, position in anchor_positions.items()
    }
    frame = HybridFrame(1, 1, wall, (150.0, 150.0))
    started = time.perf_counter()
    result = DualFirstFrameRegistrar().register(
        frame,
        reference=typed_reference,
        anchors=anchors,
        candidates=candidates,
    )
    elapsed_ms = (time.perf_counter() - started) * 1000.0
    assert result.status == "accepted", result.reason
    assert float(result.diagnostics["best_pair_confidence"]) >= 0.90
    assert float(result.diagnostics["best_shape_quality"]) >= 0.85
    # This is a regression guard against accidentally restoring an unbounded
    # multi-frame first-frame loop.  The exact runtime is intentionally loose
    # because CI machines vary; the current 300x300 fixture is ~1.8s locally.
    assert elapsed_ms < 10_000.0
    return result


def _accepted_result(candidates) -> DualFirstFrameResult:
    players = {
        "p1": PlayerLocalization(
            "p1", "observation-1", (86.0, 148.0), (86.0, 148.0), (86.0, 148.0), 0.0, 0.98, True
        ),
        "p2": PlayerLocalization(
            "p2", "observation-0", (75.0, 155.0), (75.0, 155.0), (75.0, 155.0), 0.0, 0.99, True
        ),
    }
    registration = AbsoluteRegistration(
        LocalizationResult((86.0, 148.0), 0.95),
        SimilarityTransform2D(0.0, False, 1.0, (0.0, 0.0)),
        0.0,
        "offline-fixture",
    )
    return DualFirstFrameResult("accepted", "offline-fixture", registration, players)


def test_historical_raw_single_frame_registration_and_visual_recovery():
    raw, wall = _load_sample()
    observation, candidates = _historical_candidates(raw)
    assert len(observation.candidates) >= 2
    assert candidates[0].color_features["profile"] != candidates[1].color_features["profile"]

    first_frame = _fixture_first_frame(wall, candidates)
    tracker = DualVisualTracker(max_failures=3)
    tracker.start(HybridFrame(1, 1, wall, (150.0, 150.0)), first_frame)

    good = tracker.tick(HybridFrame(2, 34, wall, (150.0, 150.0)), candidates)
    missing = tracker.tick(HybridFrame(3, 67, wall, (150.0, 150.0)), ())
    recovered = tracker.tick(HybridFrame(4, 100, wall, (150.0, 150.0)), candidates)

    assert good.status == "tracking"
    assert missing.status == "degraded"
    assert missing.diagnostics["prediction_active"] is True
    assert all(point is not None for point in missing.players.values())
    assert recovered.status == "tracking"
    assert recovered.diagnostics["prediction_active"] is False


def test_historical_raw_worker_path_stays_below_33ms_without_queueing():
    raw, wall = _load_sample()
    _, candidates = _historical_candidates(raw)
    tracker = DualVisualTracker(max_failures=3)
    tracker.start(HybridFrame(1, 1, wall, (150.0, 150.0)), _accepted_result(candidates))

    class _Recognizer:
        def extract_combined_with_processed(self, image, **kwargs):
            del image, kwargs
            return None, (wall, None)

    config = SimpleNamespace(
        dual_marker_profiles=tuple(profile.to_dict() for profile in _profiles()),
    )
    worker = Poe2DualMotionWorker(
        tracker=tracker,
        preview_provider=lambda _: raw,
        recognizer=_Recognizer(),
        monitor_config=config,
        fps=30,
        generation=1,
    )
    timings = [worker._capture_one().total_worker_ms for _ in range(5)]
    assert max(timings) < 33.0
    assert worker.completed_frames == 0  # direct replay does not fake worker-loop counters
    assert worker.dropped_results == 0
