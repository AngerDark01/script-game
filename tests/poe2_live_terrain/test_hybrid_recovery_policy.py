from auto_modules.features.poe2.live_terrain.experimental.hybrid_localization.recovery import (
    OneShotRecoveryPolicy,
)


def test_each_revision_can_be_consumed_once():
    policy = OneShotRecoveryPolicy()

    assert policy.begin() == 1
    assert policy.consume(1) is True
    assert policy.consume(1) is False
    assert policy.begin() == 2
    assert policy.consume(1) is False
    assert policy.consume(2) is True
