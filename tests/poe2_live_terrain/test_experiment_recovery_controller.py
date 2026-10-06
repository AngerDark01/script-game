from auto_modules.features.poe2.live_terrain.experimental.recovery.controller import (
    RecoveryController,
    RecoveryObservation,
)


def test_progress_observed_does_not_request_global_recovery():
    controller = RecoveryController(session_id="s1")
    decision = controller.observe(
        RecoveryObservation("occlusion", contact_evidence={"reason": "progress_observed"})
    )
    assert decision.requested is False
    assert controller.state.active is False


def test_explicit_recovery_is_claimed_once_per_episode():
    controller = RecoveryController(session_id="s1")
    first = controller.observe(
        RecoveryObservation("stalled", recovery_requested=True)
    )
    second = controller.observe(
        RecoveryObservation("stalled", recovery_requested=True)
    )
    assert first.requested is True
    assert second.suppressed is True


def test_retry_backoff_is_bounded():
    controller = RecoveryController(session_id="s1")
    first = controller.schedule_retry("worker_failed")
    second = controller.schedule_retry("worker_failed")
    assert first.retry_after_ms == 5_000
    assert second.retry_after_ms == 10_000
