import math

from auto_modules.features.poe2.live_terrain.experimental.multiplayer_follow.recovery.local_reanchor import roi_radii, accept_local_score
from auto_modules.features.poe2.live_terrain.experimental.multiplayer_follow.tracking.prediction_model import predict_position, fuse_position


def test_local_roi_is_bounded_and_score_has_recovery_thresholds():
    assert roi_radii() == (80.0, 140.0, 220.0)
    assert accept_local_score(0.60) is True
    assert accept_local_score(0.40) is False


def test_prediction_and_fusion_are_finite_and_continuous():
    predicted = predict_position((10, 20), (2, 0), (1, 0), 0.5)
    assert predicted == (10.85, 20.0)
    fused = fuse_position(predicted, (12, 20), prediction_sigma=10, observation_sigma=5)
    assert math.isfinite(fused[0])
    assert 10.85 < fused[0] < 12.0
