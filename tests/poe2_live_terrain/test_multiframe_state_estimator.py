import numpy as np

from auto_modules.features.poe2.live_terrain.experimental.multiframe_localization.state_estimator import PositionStateEstimator


def test_estimator_predicts_and_accepts_nearby_observation():
    estimator = PositionStateEstimator()
    estimator.reset((10, 10), now_ms=0)
    predicted = estimator.predict((2, 0), now_ms=1000)
    observed = estimator.observe((12.2, 10.1), covariance=np.eye(2), now_ms=1100)
    assert predicted.position[0] == 12.0
    assert observed.accepted_observation
    assert observed.position[0] == 12.2 or observed.position[0] > 12.0


def test_estimator_rejects_large_jump_without_moving_state():
    estimator = PositionStateEstimator()
    estimator.reset((0, 0))
    result = estimator.observe((100, 100), covariance=np.eye(2))
    assert not result.accepted_observation
    assert result.reason == "observation_rejected"
    assert result.position[0] == 0.0


def test_prediction_covariance_grows_with_time_low_quality_and_registration_uncertainty():
    stable = PositionStateEstimator()
    uncertain = PositionStateEstimator()
    stable.reset((0, 0), now_ms=0)
    uncertain.reset((0, 0), now_ms=0)

    stable_update = stable.predict((1, 0), quality=1.0, now_ms=100)
    uncertain_update = uncertain.predict(
        (1, 0),
        quality=0.2,
        now_ms=2000,
        registration_variance=3.0,
    )

    assert uncertain_update.covariance[0, 0] > stable_update.covariance[0, 0]
