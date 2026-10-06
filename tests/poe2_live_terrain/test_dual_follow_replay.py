from __future__ import annotations

import cv2
import numpy as np

from auto_modules.core.localization import LocalizationResult
from auto_modules.features.poe2.live_terrain.experimental.hybrid_localization.models import (
    AbsoluteRegistration,
    HybridFrame,
    SimilarityTransform2D,
)
from auto_modules.features.poe2.live_terrain.experimental.multiplayer_localization.dual_motion import (
    DualVisualTracker,
)
from auto_modules.features.poe2.live_terrain.experimental.multiplayer_localization.models import (
    DualFirstFrameResult,
    PlayerLocalization,
    PlayerMarkerCandidate,
)


def _walls() -> np.ndarray:
    image = np.zeros((96, 96), dtype=np.uint8)
    cv2.line(image, (12, 15), (12, 75), 255, 2)
    cv2.line(image, (12, 75), (80, 75), 255, 2)
    cv2.line(image, (45, 25), (73, 25), 255, 2)
    return image


def _frame(walls: np.ndarray, number: int) -> HybridFrame:
    return HybridFrame(number, number * 33, walls, (48.0, 48.0))


def _candidate(name: str, x: float, y: float) -> PlayerMarkerCandidate:
    return PlayerMarkerCandidate(name, (x, y), confidence=0.9)


def _registered(walls: np.ndarray):
    transform = SimilarityTransform2D(0.0, False, 1.0, (200.0, 300.0))
    registration = AbsoluteRegistration(
        LocalizationResult((225.0, 330.0), 0.9), transform, 1.0, "instance-1"
    )
    players = {
        name: PlayerLocalization(name, name, point, point, point, 0.0, 0.9, True)
        for name, point in {"a": (25.0, 30.0), "b": (65.0, 55.0)}.items()
    }
    return _frame(walls, 1), DualFirstFrameResult("accepted", "ok", registration, players)


def test_follow_replay_holds_one_bad_visual_frame_then_returns_to_tracking():
    walls = _walls()
    initial, result = _registered(walls)
    tracker = DualVisualTracker()
    tracker.start(initial, result)

    good = tracker.tick(
        _frame(walls, 2),
        (_candidate("a", 25.0, 30.0), _candidate("b", 65.0, 55.0)),
    )
    degraded = tracker.tick(_frame(walls, 3), ())
    recovered = tracker.tick(
        _frame(walls, 4),
        (_candidate("a", 27.0, 30.0), _candidate("b", 67.0, 55.0)),
    )

    assert good.status == "tracking"
    assert degraded.status == "degraded"
    assert degraded.diagnostics["prediction_active"] is True
    assert all(point is not None for point in degraded.players.values())
    assert recovered.status == "tracking"
    assert recovered.diagnostics["prediction_active"] is False


def test_follow_replay_holds_last_positions_when_wall_frame_is_blank():
    walls = _walls()
    initial, result = _registered(walls)
    tracker = DualVisualTracker(max_failures=2)
    tracker.start(initial, result)

    degraded = tracker.tick(_frame(np.zeros_like(walls), 2), ())
    recovered = tracker.tick(
        _frame(walls, 3),
        (_candidate("a", 25.0, 30.0), _candidate("b", 65.0, 55.0)),
    )

    assert degraded.status == "degraded"
    assert degraded.diagnostics["prediction_active"] is True
    assert all(point is not None for point in degraded.players.values())
    assert recovered.status == "tracking"
