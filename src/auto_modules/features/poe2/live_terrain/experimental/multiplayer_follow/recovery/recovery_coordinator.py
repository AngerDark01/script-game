"""Small deterministic policy for ordering visual, local and memory recovery."""

from __future__ import annotations

from dataclasses import dataclass

from .recovery_state import RecoveryState


@dataclass(frozen=True)
class RecoveryDecision:
    action: str
    state: RecoveryState
    reason: str
    cooldown_remaining_ms: int = 0


class RecoveryCoordinator:
    """Choose one bounded recovery action without performing side effects."""

    def __init__(
        self,
        *,
        memory_cooldown_ms: int = 8_000,
        stale_frame_ms: int = 500,
        prediction_limit: float = 50.0,
        failure_limit: int = 4,
    ) -> None:
        self.memory_cooldown_ms = int(memory_cooldown_ms)
        self.stale_frame_ms = int(stale_frame_ms)
        self.prediction_limit = float(prediction_limit)
        self.failure_limit = int(failure_limit)

    def decide(
        self,
        *,
        now_ms: int,
        frame_available: bool,
        frame_age_ms: float | None,
        visual_score: float | None,
        local_score: float | None,
        consecutive_visual_failures: int,
        prediction_uncertainty: float,
        last_memory_ms: int | None,
    ) -> RecoveryDecision:
        if frame_available and (frame_age_ms is None or frame_age_ms <= self.stale_frame_ms):
            if visual_score is not None and visual_score >= 0.65:
                return RecoveryDecision("visual", RecoveryState.TRACKING, "visual_accepted")
            if local_score is None or local_score < 0.55:
                return RecoveryDecision("local_visual", RecoveryState.LOCAL_REANCHORING, "new_frame_visual_retry")
            return RecoveryDecision("local_visual", RecoveryState.LOCAL_REANCHORING, "new_frame_local_retry")

        cooldown_remaining = 0
        if last_memory_ms is not None:
            cooldown_remaining = max(0, self.memory_cooldown_ms - (int(now_ms) - int(last_memory_ms)))
        memory_allowed = cooldown_remaining == 0
        threshold_reached = (
            int(consecutive_visual_failures) >= self.failure_limit
            or float(prediction_uncertainty) >= self.prediction_limit
        )
        if memory_allowed and threshold_reached:
            return RecoveryDecision("memory", RecoveryState.MEMORY_REANCHORING, "stale_frame_or_prediction_limit")
        return RecoveryDecision("predict", RecoveryState.PREDICTING, "continue_bounded_prediction", cooldown_remaining)


__all__ = ["RecoveryCoordinator", "RecoveryDecision"]
