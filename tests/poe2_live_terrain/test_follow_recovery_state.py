from auto_modules.features.poe2.live_terrain.experimental.multiplayer_follow.recovery.recovery_diagnostics import RecoveryDiagnostic
from auto_modules.features.poe2.live_terrain.experimental.multiplayer_follow.recovery.recovery_state import RecoveryLevel, RecoveryState


def test_recovery_states_are_explicit_and_ordered():
    assert RecoveryState.TRACKING.value == "tracking"
    assert RecoveryState.VISUAL_DEGRADED.value == "visual_degraded"
    assert RecoveryState.MEMORY_REANCHORING.value == "memory_reanchoring"
    assert RecoveryLevel.LOCAL.value < RecoveryLevel.MEMORY.value < RecoveryLevel.GLOBAL.value


def test_diagnostic_records_frame_and_attempt_details():
    item = RecoveryDiagnostic(
        session_id="s1",
        generation=2,
        role="role-b",
        state=RecoveryState.VISUAL_DEGRADED,
        reason="marker_missing",
        frame_available=True,
        frame_age_ms=12.0,
        candidate_count=3,
    )
    assert item.frame_available is True
    assert item.frame_age_ms == 12.0
    assert item.candidate_count == 3
    assert item.state is RecoveryState.VISUAL_DEGRADED
