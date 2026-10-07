from __future__ import annotations

from auto_modules.features.poe2.live_terrain.experimental.follow_engine.recovery.recovery_policy import (
    RecoveryAction,
    RecoveryObservation,
    RecoveryPolicy,
)
from auto_modules.features.poe2.live_terrain.experimental.multiplayer_follow.recovery.recovery_state import RecoveryState


def test_visual_frame_is_used_before_any_recovery_backend():
    policy = RecoveryPolicy()
    decision = policy.decide(RecoveryObservation(frame_available=True, frame_age_ms=33, local_attempted=False))
    assert decision.action is RecoveryAction.LOCAL_RETRY
    assert decision.state is RecoveryState.LOCAL_REANCHOR_PENDING


def test_short_visual_gap_keeps_prediction_session_alive():
    decision = RecoveryPolicy().decide(
        RecoveryObservation(frame_available=False, frame_age_ms=400, consecutive_misses=1, prediction_uncertainty=20)
    )
    assert decision.state is RecoveryState.VISUAL_DEGRADED
    assert decision.action is RecoveryAction.CONTINUE
    assert decision.keep_session is True


def test_local_success_returns_to_tracking_without_memory_or_global():
    decision = RecoveryPolicy().decide(
        RecoveryObservation(frame_available=True, frame_age_ms=700, local_attempted=True, local_succeeded=True)
    )
    assert decision.state is RecoveryState.TRACKING
    assert decision.action is RecoveryAction.CONTINUE


def test_memory_is_low_frequency_fallback_after_misses_or_uncertainty():
    decision = RecoveryPolicy().decide(
        RecoveryObservation(
            frame_available=False,
            frame_age_ms=1600,
            consecutive_misses=3,
            prediction_uncertainty=60,
            memory_cooldown_ready=True,
        )
    )
    assert decision.state is RecoveryState.MEMORY_REANCHOR_PENDING
    assert decision.action is RecoveryAction.MEMORY_REANCHOR
    assert decision.keep_session is True


def test_memory_failure_can_escalate_to_one_async_global_attempt():
    decision = RecoveryPolicy().decide(
        RecoveryObservation(
            frame_available=False,
            frame_age_ms=3200,
            prediction_uncertainty=120,
            memory_failed=True,
            global_failed=False,
        )
    )
    assert decision.state is RecoveryState.GLOBAL_REANCHOR_PENDING
    assert decision.action is RecoveryAction.GLOBAL_REANCHOR
    assert decision.keep_session is True


def test_host_session_rearm_is_separate_from_map_recovery():
    decision = RecoveryPolicy().decide(RecoveryObservation(host_session_expired=True))
    assert decision.state is RecoveryState.FOLLOW_REARMING
    assert decision.action is RecoveryAction.REARM_OUTPUT
    assert decision.keep_session is True


def test_only_explicit_user_stop_releases_dynamic_follow_session():
    for observation in (
        RecoveryObservation(frame_available=False, frame_age_ms=9000, prediction_uncertainty=500),
        RecoveryObservation(map_instance_valid=False),
        RecoveryObservation(global_in_flight=True),
    ):
        assert RecoveryPolicy().decide(observation).keep_session is True
    stopped = RecoveryPolicy().decide(RecoveryObservation(user_stop=True))
    assert stopped.action is RecoveryAction.STOP
    assert stopped.keep_session is False
