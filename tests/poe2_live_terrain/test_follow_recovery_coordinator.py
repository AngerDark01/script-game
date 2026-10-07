from auto_modules.features.poe2.live_terrain.experimental.multiplayer_follow.recovery.recovery_coordinator import RecoveryCoordinator
from auto_modules.features.poe2.live_terrain.experimental.multiplayer_follow.recovery.recovery_state import RecoveryState


def test_new_frame_prefers_visual_then_local_before_memory():
    coordinator = RecoveryCoordinator(memory_cooldown_ms=8000)
    decision = coordinator.decide(
        now_ms=10_000,
        frame_available=True,
        frame_age_ms=20,
        visual_score=0.20,
        local_score=0.60,
        consecutive_visual_failures=1,
        prediction_uncertainty=12,
        last_memory_ms=0,
    )
    assert decision.action == "local_visual"
    assert decision.state is RecoveryState.LOCAL_REANCHORING
    assert decision.action != "memory"


def test_stale_frame_can_request_memory_after_prediction_limit():
    coordinator = RecoveryCoordinator(memory_cooldown_ms=8000)
    decision = coordinator.decide(
        now_ms=20_000,
        frame_available=False,
        frame_age_ms=900,
        visual_score=None,
        local_score=None,
        consecutive_visual_failures=5,
        prediction_uncertainty=70,
        last_memory_ms=0,
    )
    assert decision.action == "memory"
    assert decision.state is RecoveryState.MEMORY_REANCHORING


def test_memory_is_blocked_by_cooldown_and_prediction_continues():
    coordinator = RecoveryCoordinator(memory_cooldown_ms=8000)
    decision = coordinator.decide(
        now_ms=5_000,
        frame_available=False,
        frame_age_ms=900,
        visual_score=None,
        local_score=None,
        consecutive_visual_failures=5,
        prediction_uncertainty=70,
        last_memory_ms=1_000,
    )
    assert decision.action == "predict"
    assert decision.state is RecoveryState.PREDICTING
