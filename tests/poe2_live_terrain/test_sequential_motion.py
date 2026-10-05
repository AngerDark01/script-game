from auto_modules.features.poe2.live_terrain.experimental.multiplayer_follow.motion_models import (
    MotionCommand,
    MotionResponse,
)
from auto_modules.features.poe2.live_terrain.experimental.multiplayer_follow.sequential_motion import (
    SequentialMotionEstimator,
    SequentialMotionState,
)


def test_estimator_accepts_valid_response_and_updates_velocity():
    estimator = SequentialMotionEstimator(min_displacement=0.5)
    estimator.reset((10.0, 20.0), now_ms=1000)
    update = estimator.apply(
        MotionCommand(1, "a", (1.0, 0.0), (0.5, 0.0), 100, 1000, "map:v1"),
        MotionResponse(1, (4.0, 0.0), 100, 1.0, 40.0, 4.0, True, "accepted"),
        now_ms=1100,
    )
    assert update.accepted
    assert update.position[0] > 10.0
    assert update.velocity[0] > 0.0
    assert update.state is SequentialMotionState.MOVING


def test_estimator_rejects_small_or_bad_response_without_jumping():
    estimator = SequentialMotionEstimator(min_displacement=1.0)
    estimator.reset((10.0, 20.0), now_ms=1000)
    update = estimator.apply(
        MotionCommand(1, "a", (1.0, 0.0), (0.5, 0.0), 100, 1000, "map:v1"),
        MotionResponse(1, (0.1, 0.0), 100, 0.0, 1.0, 0.0, False, "stalled"),
        now_ms=1100,
    )
    assert not update.accepted
    assert update.position == (10.0, 20.0)
    assert update.state is SequentialMotionState.STALLED
