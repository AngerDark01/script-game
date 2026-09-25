"""State machine coordinating bounded evidence, A/B registration and tracking."""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import StrEnum
from typing import Any

import numpy as np

from auto_modules.core.localization import LocalizationResult, transform_local_displacement
from auto_modules.features.poe2.live_terrain.experimental.hybrid_localization.models import AbsoluteRegistration

from .evidence_window import EvidenceWindow
from .local_corrector import LocalShapeCorrector
from .models import MultiFrameEvidence, PositionEstimate
from .registration_validator import RegistrationDecision, RegistrationValidator
from .rolling_submap import RollingSubmap
from .state_estimator import PositionStateEstimator
from .strategy_a import StrategyResult
from .strategy_b import CandidateSet


class LocalizationPhase(StrEnum):
    IDLE = "idle"
    ANCHORING = "anchoring"
    COLLECTING = "collecting"
    REGISTERING = "registering"
    TRACKING = "tracking"
    DEGRADED = "degraded"
    RECOVERING = "recovering"
    WAITING = "waiting"


@dataclass(frozen=True)
class LocalCorrectionPolicy:
    min_distance: float = 24.0
    max_interval_ms: int = 1500
    max_covariance: float = 64.0

    def __post_init__(self) -> None:
        if self.min_distance <= 0 or self.max_interval_ms < 1 or self.max_covariance <= 0:
            raise ValueError("local correction policy limits must be positive")

    def should_correct(
        self,
        *,
        distance: float,
        last_correction_ms: int | None,
        captured_at_ms: int,
        covariance: np.ndarray | None,
    ) -> bool:
        if distance >= self.min_distance:
            return True
        if last_correction_ms is not None and captured_at_ms - last_correction_ms >= self.max_interval_ms:
            return True
        if covariance is not None and float(np.max(np.linalg.eigvalsh(covariance))) >= self.max_covariance:
            return True
        return False


@dataclass(frozen=True)
class RegistrationRequest:
    instance_id: str
    recovery_revision: int
    evidence_version: int
    segment_id: int
    frames: tuple[MultiFrameEvidence, ...]
    anchor: Any
    reference: Any

    @property
    def token(self) -> tuple[str, int, int, int]:
        return self.instance_id, self.recovery_revision, self.evidence_version, self.segment_id


@dataclass(frozen=True)
class GlobalStrategyOutcome:
    request: RegistrationRequest
    strategy_a: Any | None
    strategy_b: Any | None
    registration: AbsoluteRegistration | None
    source: str
    strategy_a_decision: RegistrationDecision | None = None
    strategy_b_decision: RegistrationDecision | None = None
    diagnostics: dict[str, object] | None = None


class _FrozenWindow:
    def __init__(self, frames: tuple[MultiFrameEvidence, ...], version: int) -> None:
        self._frames = frames
        self.version = int(version)

    def snapshot(self) -> tuple[MultiFrameEvidence, ...]:
        return self._frames


class MultiframeLocalizationCoordinator:
    def __init__(
        self,
        *,
        instance_id: str,
        window: EvidenceWindow | None = None,
        submap: RollingSubmap | None = None,
        estimator: PositionStateEstimator | None = None,
        strategy_a: Any | None = None,
        strategy_b: Any | None = None,
        reference: Any | None = None,
        max_tracking_failures: int = 3,
        local_corrector: Any | None = None,
        correction_policy: LocalCorrectionPolicy | None = None,
        registration_validator: RegistrationValidator | None = None,
        max_correction_failures: int = 3,
        retry_min_distance: float = 16.0,
        retry_min_keyframes: int = 2,
        retry_min_interval_ms: int = 1000,
    ) -> None:
        if not instance_id:
            raise ValueError("instance_id is required")
        if int(max_tracking_failures) < 1 or int(max_correction_failures) < 1:
            raise ValueError("tracking failure limits must be positive")
        if float(retry_min_distance) <= 0 or int(retry_min_keyframes) < 1 or int(retry_min_interval_ms) < 0:
            raise ValueError("registration retry limits are invalid")
        self.instance_id = str(instance_id)
        self.window = window or EvidenceWindow()
        self.submap = submap or RollingSubmap()
        self.estimator = estimator or PositionStateEstimator()
        self.strategy_a = strategy_a
        self.strategy_b = strategy_b
        self.reference = reference
        self.max_tracking_failures = int(max_tracking_failures)
        self.local_corrector = local_corrector
        self.correction_policy = correction_policy or LocalCorrectionPolicy()
        self.registration_validator = registration_validator or RegistrationValidator()
        self.max_correction_failures = int(max_correction_failures)
        self.strategy_a_enabled = strategy_a is not None
        self.strategy_b_enabled = strategy_b is not None
        self.phase = LocalizationPhase.IDLE
        self.anchor = None
        self.registration: AbsoluteRegistration | None = None
        self.registration_version = 0
        self.recovery_revision = 0
        self.last_estimate: PositionEstimate | None = None
        self.last_strategy_result = None
        self.last_strategy_a_result = None
        self.last_strategy_b_result = None
        self._failure_count = 0
        self._correction_failures = 0
        self._distance_since_correction = 0.0
        self._last_correction_ms: int | None = None
        self._last_correction_reason = ""
        self._pending_token: tuple[str, int, int, int] | None = None
        self._last_registration_version_attempted = -1
        self._last_confirmed_ms: int | None = None
        self._latest_frame_ms: int | None = None
        self._pending_registration_motion: list[tuple[tuple[float, float], float, int]] = []
        self._pending_segment_evidence: list[MultiFrameEvidence] = []
        self._last_registration_attempt_travel = 0.0
        self._last_registration_attempt_frame_count = 0
        self._last_registration_attempt_ms: int | None = None
        self._registration_retry_blocked = False
        self.last_registration_diagnostics: dict[str, object] = {}
        self.retry_min_distance = float(retry_min_distance)
        self.retry_min_keyframes = int(retry_min_keyframes)
        self.retry_min_interval_ms = int(retry_min_interval_ms)

    def set_strategies_enabled(self, *, strategy_a: bool, strategy_b: bool) -> None:
        if not strategy_a and not strategy_b:
            raise ValueError("at least one global strategy must be enabled")
        self.strategy_a_enabled = bool(strategy_a) and self.strategy_a is not None
        self.strategy_b_enabled = bool(strategy_b) and self.strategy_b is not None
        if not self.strategy_a_enabled and not self.strategy_b_enabled:
            raise ValueError("selected strategies are not available")

    def start(self) -> None:
        self.phase = LocalizationPhase.ANCHORING

    def stop(self) -> None:
        self.phase = LocalizationPhase.IDLE
        self._pending_token = None

    def reset(self) -> None:
        self.stop()
        self.anchor = None
        self.registration = None
        self.registration_version = 0
        self.recovery_revision = 0
        self.last_estimate = None
        self.last_strategy_result = None
        self.last_strategy_a_result = None
        self.last_strategy_b_result = None
        self._failure_count = 0
        self._correction_failures = 0
        self._distance_since_correction = 0.0
        self._last_correction_ms = None
        self._last_correction_reason = ""
        self._last_registration_version_attempted = -1
        self._last_confirmed_ms = None
        self._latest_frame_ms = None
        self._pending_registration_motion.clear()
        self._pending_segment_evidence.clear()
        self._last_registration_attempt_travel = 0.0
        self._last_registration_attempt_frame_count = 0
        self._last_registration_attempt_ms = None
        self._registration_retry_blocked = False
        self.last_registration_diagnostics = {}
        self.window.clear("reset", reset_segment=True)
        for strategy in (self.strategy_a, self.strategy_b):
            reset_strategy = getattr(strategy, "reset", None)
            if callable(reset_strategy):
                reset_strategy()

    def accept_anchor(self, anchor: Any) -> None:
        if self.phase not in {LocalizationPhase.ANCHORING, LocalizationPhase.RECOVERING}:
            raise RuntimeError("anchor is only accepted while anchoring or recovering")
        if getattr(anchor, "area_instance", None) != self.instance_id:
            self.phase = LocalizationPhase.WAITING
            raise ValueError("anchor instance does not match coordinator")
        self.anchor = anchor
        self.window.clear("new_anchor")
        self._last_registration_version_attempted = -1
        self.phase = LocalizationPhase.COLLECTING

    def anchor_failed(self, reason: str) -> PositionEstimate:
        self.phase = LocalizationPhase.WAITING
        return self._estimate(reason, status="waiting")

    def ingest(self, evidence: MultiFrameEvidence, *, defer_registration: bool = False) -> PositionEstimate:
        if self.phase in {LocalizationPhase.IDLE, LocalizationPhase.WAITING}:
            return self._estimate("not_collecting", status="waiting")
        self._latest_frame_ms = evidence.frame.captured_at_ms
        if self.phase is LocalizationPhase.REGISTERING:
            if (
                evidence.segment_id == self.window.segment_id
                and evidence.motion.accepted
                and evidence.motion.shift is not None
            ):
                self._pending_registration_motion.append(
                    (evidence.motion.shift, evidence.motion.quality, evidence.frame.captured_at_ms)
                )
            else:
                # Do not mutate the frozen window while a registration worker
                # is evaluating it. A segment change would invalidate the
                # token and make the finished result unusable.
                self._pending_segment_evidence.append(evidence)
            return self._estimate("registration_in_progress", status="registering")
        accepted_keyframe = self.window.append(evidence)
        if self.phase in {LocalizationPhase.ANCHORING, LocalizationPhase.RECOVERING}:
            return self._estimate("awaiting_memory_anchor", status="waiting")
        if self.phase in {LocalizationPhase.TRACKING, LocalizationPhase.DEGRADED}:
            return self._run_tracking(evidence)
        if self.phase is not LocalizationPhase.COLLECTING:
            return self._estimate("not_collecting", status="waiting")
        if not accepted_keyframe:
            return self._estimate("collecting_evidence", status="collecting")
        if defer_registration:
            return self._estimate("registration_ready", status="collecting")
        request = self.prepare_registration_request()
        if request is None:
            return self._estimate("collecting_evidence", status="collecting")
        return self.apply_registration_outcome(self.evaluate_registration(request))

    def prepare_registration_request(self) -> RegistrationRequest | None:
        if self.phase is not LocalizationPhase.COLLECTING or self.anchor is None or self.reference is None:
            return None
        frames = self.window.snapshot()
        if not frames or self.window.version == self._last_registration_version_attempted:
            return None
        if not self.strategy_a_enabled and not self.strategy_b_enabled:
            return None
        required_frames = self.minimum_registration_frames
        if len(frames) < required_frames:
            return None
        if self._registration_retry_blocked and self.minimum_registration_frames >= 3:
            travel = self.window.travel_distance
            new_frames = len(frames) - self._last_registration_attempt_frame_count
            latest_ms = int(frames[-1].frame.captured_at_ms)
            elapsed = (
                latest_ms - self._last_registration_attempt_ms
                if self._last_registration_attempt_ms is not None
                else self.retry_min_interval_ms
            )
            if (
                travel - self._last_registration_attempt_travel < self.retry_min_distance
                and new_frames < self.retry_min_keyframes
                and elapsed < self.retry_min_interval_ms
            ):
                return None
        request = RegistrationRequest(
            self.instance_id,
            self.recovery_revision,
            self.window.version,
            self.window.segment_id,
            frames,
            self.anchor,
            self.reference,
        )
        self._pending_token = request.token
        self._pending_registration_motion.clear()
        self._last_registration_version_attempted = self.window.version
        self._last_registration_attempt_travel = self.window.travel_distance
        self._last_registration_attempt_frame_count = len(frames)
        self._last_registration_attempt_ms = int(frames[-1].frame.captured_at_ms)
        self.phase = LocalizationPhase.REGISTERING
        return request

    @property
    def minimum_registration_frames(self) -> int:
        """Return the strictest enabled strategy readiness requirement.

        Custom strategies may omit the optional contract and remain compatible
        with the original one-frame coordinator behavior. Built-in strategies
        expose their actual multi-frame requirements so expensive searches are
        never started on a single keyframe.
        """
        requirements: list[int] = []
        for enabled, strategy in (
            (self.strategy_a_enabled, self.strategy_a),
            (self.strategy_b_enabled, self.strategy_b),
        ):
            if not enabled or strategy is None:
                continue
            value = getattr(strategy, "minimum_evidence_frames", 1)
            if callable(value):
                value = value()
            try:
                requirements.append(max(1, int(value)))
            except (TypeError, ValueError):
                requirements.append(1)
        return max(requirements, default=1)

    def evaluate_registration(self, request: RegistrationRequest) -> GlobalStrategyOutcome:
        frozen_window = _FrozenWindow(request.frames, request.evidence_version)
        self._last_correction_reason = ""
        result_a = None
        result_b = None
        registration_a = None
        registration_b = None
        registration = None
        source = "none"
        decision_a = None
        decision_b = None
        diagnostics: dict[str, object] = {}
        if self.strategy_a_enabled and self.strategy_a is not None:
            try:
                result_a = self.strategy_a.evaluate(
                    frozen_window,
                    RollingSubmap(max_width=self.submap.max_width, max_height=self.submap.max_height),
                    anchor=request.anchor,
                    reference=request.reference,
                )
            except Exception as exc:
                result_a = StrategyResult.rejected(
                    request.evidence_version,
                    f"strategy_exception:{type(exc).__name__}:{exc}",
                )
            candidate = getattr(result_a, "candidate", None)
            if getattr(result_a, "status", None) == "confirmed" and isinstance(candidate, AbsoluteRegistration):
                support_frames = getattr(result_a, "support_frames", ())
                if not support_frames:
                    support_frames = tuple(item.frame.frame_id for item in request.frames)
                decision_a = self.registration_validator.validate(
                    candidate,
                    anchor=request.anchor,
                    frames=request.frames,
                    support_frames=support_frames,
                    holdout_error=float(getattr(result_a, "holdout_error", 0.0)),
                    best_error=float(getattr(result_a, "best_error", 0.0)),
                    second_error=getattr(result_a, "second_error", None),
                )
                self._last_correction_reason = decision_a.reason
                registration_a = decision_a.candidate
                if registration_a is None and isinstance(result_a, StrategyResult):
                    result_a = replace(
                        result_a,
                        status="rejected",
                        reason=f"validator:{decision_a.reason}",
                    )
                diagnostics["strategy_a_validation"] = dict(decision_a.diagnostics)
                diagnostics["strategy_a_rejection"] = decision_a.reason
            elif result_a is not None:
                diagnostics["strategy_a_rejection"] = getattr(result_a, "reason", "not_confirmed")
        if self.strategy_b_enabled and self.strategy_b is not None:
            boundary = getattr(request.reference, "wall_layer", request.reference)
            try:
                from auto_modules.features.poe2.live_terrain.experimental.hybrid_localization.absolute_registrar import reference_boundary_layer
                if hasattr(request.reference, "walkable_mask"):
                    boundary = reference_boundary_layer(request.reference)
            except (ImportError, TypeError, ValueError):
                pass
            boundary, reference_origin = self._bounded_strategy_b_reference(
                np.asarray(boundary), request
            )
            try:
                update_kwargs = {
                    "anchor": request.anchor,
                    "reference_boundary": boundary,
                    "evidence_version": request.evidence_version,
                }
                try:
                    result_b = self.strategy_b.update(
                        request.frames,
                        reference_origin=reference_origin,
                        **update_kwargs,
                    )
                except TypeError as exc:
                    if "reference_origin" not in str(exc):
                        raise
                    result_b = self.strategy_b.update(request.frames, **update_kwargs)
            except Exception as exc:
                result_b = CandidateSet((), request.evidence_version)
                self._last_correction_reason = f"strategy_b_exception:{type(exc).__name__}:{exc}"
            if self.strategy_b.confirmable(result_b):
                best = result_b.best
                if best is not None:
                    candidate_registration = AbsoluteRegistration(
                        result=LocalizationResult(
                            position=best.position,
                            confidence=max(0.0, min(1.0, float(best.score))),
                            source="multiframe_strategy_b",
                            registration_valid=True,
                        ),
                        transform=best.transform,
                        anchor_error=float(np.hypot(best.position[0] - request.anchor.position[0], best.position[1] - request.anchor.position[1])),
                        area_instance=request.instance_id,
                        diagnostics={"evidence_version": request.evidence_version, "candidate_count": len(result_b.candidates)},
                    )
                    second_error = result_b.candidates[1].error if len(result_b.candidates) > 1 else None
                    decision_b = self.registration_validator.validate(
                        candidate_registration,
                        anchor=request.anchor,
                        frames=request.frames,
                        support_frames=best.support_frames,
                        holdout_error=getattr(best, "holdout_error", float("inf")),
                        best_error=best.error,
                        second_error=second_error,
                        peer=registration_a,
                    )
                    self._last_correction_reason = decision_b.reason
                    registration_b = decision_b.candidate
                    diagnostics["strategy_b_validation"] = dict(decision_b.diagnostics)
                    diagnostics["strategy_b_rejection"] = decision_b.reason
            if result_b is not None:
                candidates = tuple(getattr(result_b, "candidates", ()) or ())
                diagnostics["strategy_b_candidate_count"] = len(candidates)
                diagnostics["strategy_b_candidates"] = [
                    {
                        "angle": float(item.transform.angle_degrees),
                        "scale": float(item.transform.scale),
                        "reflect": bool(item.transform.reflect_horizontal),
                        "position": [float(item.position[0]), float(item.position[1])],
                        "error": float(item.error),
                        "score": float(item.score),
                        "holdout_error": float(item.holdout_error),
                        "support_frames": list(item.support_frames),
                    }
                    for item in tuple(getattr(result_b, "candidates", ()) or ())[:12]
                ]
        if registration_a is not None and registration_b is not None:
            if float(registration_b.result.confidence) > float(registration_a.result.confidence):
                registration = registration_b
                source = "multiframe_strategy_b"
            else:
                registration = registration_a
                source = "multiframe_strategy_a"
        elif registration_a is not None:
            registration = registration_a
            source = "multiframe_strategy_a"
        elif registration_b is not None:
            registration = registration_b
            source = "multiframe_strategy_b"
        diagnostics["selected_source"] = source
        return GlobalStrategyOutcome(
            request,
            result_a,
            result_b,
            registration,
            source,
            decision_a,
            decision_b,
            diagnostics,
        )

    def _bounded_strategy_b_reference(
        self,
        boundary: np.ndarray,
        request: RegistrationRequest,
    ) -> tuple[np.ndarray, tuple[float, float]]:
        """Keep Strategy B's distance fields inside the anchor neighbourhood."""
        if boundary.ndim != 2 or boundary.size == 0:
            return boundary, (0.0, 0.0)
        max_extent = max(
            max(int(item.frame.wall_mask.shape[0]), int(item.frame.wall_mask.shape[1]))
            for item in request.frames
        )
        coarse_scales = getattr(self.strategy_b, "coarse_scales", (1.5,))
        max_scale = max((float(value) for value in coarse_scales), default=1.5)
        radius = max(256, int(np.ceil(max_extent * max_scale * 1.75)))
        anchor_x = int(round(float(request.anchor.position[0])))
        anchor_y = int(round(float(request.anchor.position[1])))
        x0 = max(0, anchor_x - radius)
        y0 = max(0, anchor_y - radius)
        x1 = min(boundary.shape[1], anchor_x + radius + 1)
        y1 = min(boundary.shape[0], anchor_y + radius + 1)
        return np.array(boundary[y0:y1, x0:x1], copy=True), (float(x0), float(y0))

    def apply_registration_outcome(self, outcome: GlobalStrategyOutcome) -> PositionEstimate:
        request = outcome.request
        current_token = (self.instance_id, self.recovery_revision, self.window.version, self.window.segment_id)
        if self._pending_token != request.token or request.token != current_token:
            if self.phase is LocalizationPhase.REGISTERING:
                self.phase = LocalizationPhase.COLLECTING
            self._pending_token = None
            return self._estimate("stale_registration_result", status="collecting")
        self._pending_token = None
        self.last_strategy_a_result = outcome.strategy_a
        self.last_strategy_b_result = outcome.strategy_b
        self.last_strategy_result = outcome.strategy_b or outcome.strategy_a
        self.last_registration_diagnostics = dict(outcome.diagnostics or {})
        if outcome.registration is not None:
            confirmed_position = outcome.registration.result.position
            if confirmed_position is None:
                self.phase = LocalizationPhase.COLLECTING
                return self._estimate("registration_missing_position", status="collecting")
            estimate = self.confirm(
                outcome.registration,
                confirmed_position,
                source=outcome.source,
                now_ms=max(item.frame.captured_at_ms for item in request.frames),
            )
            if self._pending_registration_motion:
                for shift, quality, captured_at_ms in self._pending_registration_motion:
                    estimate = self._predict_registered_shift(shift, quality=quality, captured_at_ms=captured_at_ms)
                self._pending_registration_motion.clear()
            if self._pending_segment_evidence:
                self._replay_pending_segment()
                return self._estimate(
                    "segment_changed_re_registration",
                    position=estimate.position,
                    velocity=estimate.velocity,
                    covariance=estimate.covariance,
                    status="collecting",
                    source=estimate.source,
                    fresh=False,
                )
            self._registration_retry_blocked = False
            return estimate
        self.phase = LocalizationPhase.COLLECTING
        self._registration_retry_blocked = True
        self._replay_pending_segment()
        return self._estimate(
            self._last_correction_reason or "global_registration_ambiguous",
            status="collecting",
        )

    def _replay_pending_segment(self) -> None:
        """Move evidence captured during a frozen search into a new segment."""
        pending = tuple(self._pending_segment_evidence)
        if not pending:
            return
        self._pending_segment_evidence.clear()
        self.window.clear("registration_segment_changed")
        for evidence in pending:
            self.window.append(evidence)
        self._last_registration_version_attempted = -1
        self._registration_retry_blocked = False

    def confirm(self, registration: Any, position: tuple[float, float], *, source: str = "multiframe_global", now_ms: int | None = None) -> PositionEstimate:
        if self.anchor is None:
            raise RuntimeError("cannot confirm without anchor")
        self.registration = registration
        self.registration_version += 1
        update = self.estimator.reset(position, now_ms=now_ms)
        self.phase = LocalizationPhase.TRACKING
        self._failure_count = 0
        self._correction_failures = 0
        self._distance_since_correction = 0.0
        self._last_correction_ms = now_ms
        self._last_confirmed_ms = now_ms if now_ms is not None else self._latest_frame_ms
        return self._estimate("global_registration_confirmed", position=update.position, velocity=update.velocity, covariance=update.covariance, status="confirmed", source=source, fresh=True)

    def begin_recovery(self, reason: str) -> None:
        if self.phase is LocalizationPhase.RECOVERING:
            return
        self.recovery_revision += 1
        self.anchor = None
        self.registration = None
        self.phase = LocalizationPhase.RECOVERING
        self._pending_token = None
        self._pending_registration_motion.clear()
        self._last_registration_version_attempted = -1
        self._correction_failures = 0
        self._distance_since_correction = 0.0
        self._last_correction_ms = None
        self.window.clear(reason)

    def _run_tracking(self, evidence: MultiFrameEvidence) -> PositionEstimate:
        motion = evidence.motion
        if motion.accepted and motion.shift is not None and self.registration is not None:
            self._failure_count = 0
            self.phase = LocalizationPhase.TRACKING
            prediction = self._predict_registered_shift(
                motion.shift,
                quality=motion.quality,
                captured_at_ms=evidence.frame.captured_at_ms,
            )
            self._distance_since_correction += float(np.hypot(*motion.shift))
            if (
                self.local_corrector is None
                or self.reference is None
                or prediction.position is None
                or not isinstance(self.registration, AbsoluteRegistration)
                or not self.correction_policy.should_correct(
                    distance=self._distance_since_correction,
                    last_correction_ms=self._last_correction_ms,
                    captured_at_ms=evidence.frame.captured_at_ms,
                    covariance=prediction.covariance,
                )
            ):
                return prediction
            correction = self.local_corrector.correct(
                frame=evidence.frame,
                observed_mask=evidence.observed_mask,
                predicted_position=prediction.position,
                registration=self.registration,
                reference=self.reference,
            )
            self._last_correction_reason = correction.reason
            if not correction.accepted or correction.position is None or correction.transform is None:
                return self._handle_correction_failure(prediction, correction.reason)
            update = self.estimator.observe(
                correction.position,
                covariance=correction.covariance,
                now_ms=evidence.frame.captured_at_ms,
            )
            if not update.accepted_observation:
                return self._handle_correction_failure(prediction, update.reason)
            self.registration = replace(
                self.registration,
                result=LocalizationResult(
                    update.position,
                    max(0.0, min(1.0, float(getattr(correction.score, "score", motion.quality)))),
                    source="visual_local_correction",
                    registration_valid=True,
                ),
                transform=correction.transform,
            )
            self.registration_version += 1
            self._correction_failures = 0
            self._distance_since_correction = 0.0
            self._last_correction_ms = evidence.frame.captured_at_ms
            self._last_confirmed_ms = evidence.frame.captured_at_ms
            self.phase = LocalizationPhase.TRACKING
            return self._estimate(
                "local_shape_correction",
                position=update.position,
                velocity=update.velocity,
                covariance=update.covariance,
                status="confirmed",
                source="visual_local_correction",
                fresh=True,
            )
        self._failure_count += 1
        if self._failure_count >= self.max_tracking_failures:
            self.begin_recovery("tracking_failure_limit")
            return self._estimate("tracking_failure_limit", status="recovering", fresh=False)
        self.phase = LocalizationPhase.DEGRADED
        return self._estimate("tracking_evidence_rejected", status="predicted", fresh=False)

    def _handle_correction_failure(self, prediction: PositionEstimate, reason: str) -> PositionEstimate:
        self._correction_failures += 1
        if self._correction_failures >= self.max_correction_failures:
            self.begin_recovery("local_correction_failure_limit")
            return self._estimate("local_correction_failure_limit", status="recovering", fresh=False)
        self.phase = LocalizationPhase.DEGRADED
        return self._estimate(
            f"local_correction_rejected:{reason}",
            position=prediction.position,
            velocity=prediction.velocity,
            covariance=prediction.covariance,
            status="predicted",
            source="visual_prediction",
            fresh=False,
        )

    def _predict_registered_shift(self, shift: tuple[float, float], *, quality: float, captured_at_ms: int) -> PositionEstimate:
            transform = getattr(self.registration, "transform", None)
            if transform is None:
                transformed = shift
            else:
                transformed = transform_local_displacement(
                    shift,
                    angle_degrees=transform.angle_degrees,
                    reflect_horizontal=transform.reflect_horizontal,
                    scale=transform.scale,
                )
            delta = (-transformed[0], -transformed[1])
            moving = float(np.hypot(*shift)) > 0.2
            update = self.estimator.predict(delta, quality=quality, now_ms=captured_at_ms)
            if moving and transform is not None and isinstance(self.registration, AbsoluteRegistration):
                self._last_confirmed_ms = captured_at_ms
                self.registration = replace(
                    self.registration,
                    result=LocalizationResult(update.position, max(0.0, min(1.0, quality)), source="visual_f2f", registration_valid=True),
                    transform=replace(transform, translation=(transform.translation[0] + delta[0], transform.translation[1] + delta[1])),
                )
            return self._estimate(
                "visual_displacement" if moving else "stationary",
                position=update.position,
                velocity=update.velocity,
                covariance=update.covariance,
                status="confirmed",
                source="visual_f2f" if moving else "stationary",
                fresh=moving,
            )

    def _estimate(self, reason: str, *, position=None, velocity=None, covariance=None, status: str = "ambiguous", source: str = "multiframe", fresh: bool | None = None) -> PositionEstimate:
        current = position if position is not None else self.estimator.position
        candidates = ()
        raw_candidates = getattr(self.last_strategy_b_result or self.last_strategy_result, "candidates", ())
        if raw_candidates:
            candidates = tuple(region for item in raw_candidates if (region := item.region()) is not None)
        if fresh is None:
            fresh = status == "confirmed"
        age_ms = 0
        if self._latest_frame_ms is not None and self._last_confirmed_ms is not None:
            age_ms = max(0, self._latest_frame_ms - self._last_confirmed_ms)
        estimate = PositionEstimate(
            status,
            current,
            velocity,
            covariance,
            candidates,
            self.instance_id,
            self.registration_version,
            self.window.version,
            fresh,
            age_ms,
            source,
            reason,
            {
                "phase": self.phase.value,
                "tracking_failures": self._failure_count,
                "correction_failures": self._correction_failures,
                "distance_since_correction": self._distance_since_correction,
                "last_correction_reason": self._last_correction_reason,
                "captured_at_ms": self._latest_frame_ms or 0,
                "keyframe_count": len(self.window.snapshot()),
                "segment_id": self.window.segment_id,
                "strategy_a_status": getattr(self.last_strategy_a_result, "status", None),
                "strategy_b_candidates": len(getattr(self.last_strategy_b_result, "candidates", ())),
                "registration_diagnostics": dict(self.last_registration_diagnostics),
            },
        )
        self.last_estimate = estimate
        return estimate


__all__ = ["GlobalStrategyOutcome", "LocalCorrectionPolicy", "LocalizationPhase", "MultiframeLocalizationCoordinator", "RegistrationRequest"]
