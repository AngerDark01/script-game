"""Pure L0-L3 recovery policy for continuous follow sessions."""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import StrEnum

from ...multiplayer_follow.recovery.recovery_state import RecoveryLevel, RecoveryState


class RecoveryAction(StrEnum):
    CONTINUE = "continue"
    LOCAL_RETRY = "local_retry"
    MEMORY_REANCHOR = "memory_reanchor"
    GLOBAL_REANCHOR = "global_reanchor"
    REARM_OUTPUT = "rearm_output"
    HOLD = "hold"
    STOP = "stop"


@dataclass(frozen=True, slots=True)
class RecoveryPolicyConfig:
    visual_healthy_ms: float = 250.0
    visual_degraded_ms: float = 600.0
    local_trigger_ms: float = 600.0
    memory_trigger_ms: float = 1500.0
    global_trigger_ms: float = 3000.0
    memory_uncertainty: float = 50.0
    global_uncertainty: float = 100.0
    memory_miss_count: int = 3

    def __post_init__(self) -> None:
        values = (
            self.visual_healthy_ms,
            self.visual_degraded_ms,
            self.local_trigger_ms,
            self.memory_trigger_ms,
            self.global_trigger_ms,
            self.memory_uncertainty,
            self.global_uncertainty,
        )
        if not all(math.isfinite(float(value)) and float(value) >= 0.0 for value in values):
            raise ValueError("recovery thresholds must be finite and non-negative")
        if not self.visual_healthy_ms <= self.visual_degraded_ms <= self.local_trigger_ms <= self.memory_trigger_ms <= self.global_trigger_ms:
            raise ValueError("recovery time thresholds must be ordered")
        if not self.memory_uncertainty <= self.global_uncertainty or self.memory_miss_count < 1:
            raise ValueError("recovery uncertainty/count thresholds are invalid")


@dataclass(frozen=True, slots=True)
class RecoveryObservation:
    session_active: bool = True
    user_stop: bool = False
    frame_available: bool = False
    frame_age_ms: float | None = None
    visual_match: bool = False
    local_attempted: bool = False
    local_succeeded: bool = False
    memory_in_flight: bool = False
    memory_succeeded: bool = False
    memory_failed: bool = False
    global_in_flight: bool = False
    global_succeeded: bool = False
    global_failed: bool = False
    map_instance_valid: bool = True
    transform_valid: bool = True
    memory_cooldown_ready: bool = False
    consecutive_misses: int = 0
    prediction_uncertainty: float = 0.0
    host_session_expired: bool = False

    def __post_init__(self) -> None:
        if self.frame_age_ms is not None and (not math.isfinite(float(self.frame_age_ms)) or float(self.frame_age_ms) < 0.0):
            raise ValueError("frame_age_ms must be finite and non-negative")
        if self.consecutive_misses < 0 or not math.isfinite(float(self.prediction_uncertainty)) or self.prediction_uncertainty < 0.0:
            raise ValueError("recovery observation counters are invalid")
        object.__setattr__(self, "consecutive_misses", int(self.consecutive_misses))
        object.__setattr__(self, "prediction_uncertainty", float(self.prediction_uncertainty))


@dataclass(frozen=True, slots=True)
class RecoveryDecision:
    state: RecoveryState
    level: RecoveryLevel
    action: RecoveryAction
    reason: str
    keep_session: bool = True

    @property
    def stops_session(self) -> bool:
        return not self.keep_session


class RecoveryPolicy:
    def __init__(self, config: RecoveryPolicyConfig | None = None) -> None:
        self.config = config or RecoveryPolicyConfig()

    def decide(self, observation: RecoveryObservation) -> RecoveryDecision:
        cfg = self.config
        if observation.user_stop:
            return RecoveryDecision(RecoveryState.FOLLOW_HOLD, RecoveryLevel.VISUAL, RecoveryAction.STOP, "user_stop", False)
        if not observation.session_active:
            return RecoveryDecision(RecoveryState.FOLLOW_HOLD, RecoveryLevel.VISUAL, RecoveryAction.HOLD, "session_inactive", True)
        if observation.host_session_expired:
            return RecoveryDecision(RecoveryState.FOLLOW_REARMING, RecoveryLevel.VISUAL, RecoveryAction.REARM_OUTPUT, "host_session_expired", True)

        if observation.global_succeeded or observation.memory_succeeded or observation.local_succeeded:
            source = "global_recovered" if observation.global_succeeded else "memory_recovered" if observation.memory_succeeded else "local_recovered"
            return RecoveryDecision(RecoveryState.TRACKING, RecoveryLevel.VISUAL, RecoveryAction.CONTINUE, source, True)

        if observation.global_in_flight:
            return RecoveryDecision(RecoveryState.GLOBAL_REANCHORING, RecoveryLevel.GLOBAL, RecoveryAction.HOLD, "global_reanchor_in_flight", True)
        if observation.memory_in_flight:
            return RecoveryDecision(RecoveryState.MEMORY_REANCHORING, RecoveryLevel.MEMORY, RecoveryAction.HOLD, "memory_reanchor_in_flight", True)

        if not observation.map_instance_valid or not observation.transform_valid:
            return RecoveryDecision(RecoveryState.GLOBAL_REANCHOR_PENDING, RecoveryLevel.GLOBAL, RecoveryAction.GLOBAL_REANCHOR, "map_or_transform_invalid", True)

        age = float("inf") if observation.frame_age_ms is None else float(observation.frame_age_ms)
        if observation.visual_match and age <= cfg.visual_degraded_ms:
            return RecoveryDecision(RecoveryState.TRACKING, RecoveryLevel.VISUAL, RecoveryAction.CONTINUE, "visual_match", True)

        # A fresh frame must be exhausted by visual/ROI matching before memory.
        if observation.frame_available and not observation.local_attempted:
            return RecoveryDecision(RecoveryState.LOCAL_REANCHOR_PENDING, RecoveryLevel.LOCAL, RecoveryAction.LOCAL_RETRY, "new_frame_local_retry", True)
        if observation.frame_available and age <= cfg.memory_trigger_ms and not observation.memory_failed:
            return RecoveryDecision(RecoveryState.PREDICTING, RecoveryLevel.VISUAL, RecoveryAction.CONTINUE, "prediction_after_visual_miss", True)

        memory_due = (
            observation.memory_cooldown_ready
            and (
                observation.consecutive_misses >= cfg.memory_miss_count
                or observation.prediction_uncertainty >= cfg.memory_uncertainty
                or age >= cfg.memory_trigger_ms
            )
        )
        if memory_due and not observation.memory_failed:
            return RecoveryDecision(RecoveryState.MEMORY_REANCHOR_PENDING, RecoveryLevel.MEMORY, RecoveryAction.MEMORY_REANCHOR, "memory_threshold_reached", True)

        global_due = (
            observation.global_failed
            or age >= cfg.global_trigger_ms
            or observation.prediction_uncertainty >= cfg.global_uncertainty
            or observation.memory_failed and not observation.memory_cooldown_ready
        )
        if global_due:
            return RecoveryDecision(RecoveryState.GLOBAL_REANCHOR_PENDING, RecoveryLevel.GLOBAL, RecoveryAction.GLOBAL_REANCHOR, "global_threshold_reached", True)

        if age > cfg.visual_healthy_ms or observation.consecutive_misses:
            return RecoveryDecision(RecoveryState.VISUAL_DEGRADED, RecoveryLevel.VISUAL, RecoveryAction.CONTINUE, "visual_degraded_prediction", True)
        return RecoveryDecision(RecoveryState.TRACKING, RecoveryLevel.VISUAL, RecoveryAction.CONTINUE, "tracking", True)


__all__ = [
    "RecoveryAction",
    "RecoveryDecision",
    "RecoveryObservation",
    "RecoveryPolicy",
    "RecoveryPolicyConfig",
]
