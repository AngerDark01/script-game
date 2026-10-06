from auto_modules.features.poe2.live_terrain.experimental.follow.observation_fusion import (
    FusedObservation,
    fuse_observation,
)


def test_fresh_visual_observation_wins_over_prediction():
    visual = FusedObservation((1, 2), "visual", 0.5, 100)
    predicted = FusedObservation((5, 6), "command_prediction", 3.0, 100)
    assert fuse_observation(visual=visual, predicted=predicted, now_ms=200) is visual


def test_stale_visual_observation_falls_back_to_prediction():
    visual = FusedObservation((1, 2), "visual", 0.5, 100)
    predicted = FusedObservation((5, 6), "command_prediction", 3.0, 100)
    assert fuse_observation(visual=visual, predicted=predicted, now_ms=900) is predicted
