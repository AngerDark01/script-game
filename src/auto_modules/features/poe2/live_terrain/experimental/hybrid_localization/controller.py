"""State machine that composes one-shot anchors with visual local tracking."""

from __future__ import annotations

from typing import Any, Mapping

from auto_modules.core.localization import TrajectoryBuffer

from .contracts import AbsoluteRegistrar, AnchorProvider, LocalTracker
from .models import (
    AbsoluteRegistration,
    HybridFrame,
    HybridLocalizationMode,
    HybridLocalizationState,
)
from .recovery import OneShotRecoveryPolicy


class HybridLocalizationController:
    def __init__(
        self,
        *,
        expected_instance_id: str,
        reference: Any,
        anchor_provider: AnchorProvider,
        absolute_registrar: AbsoluteRegistrar,
        local_tracker: LocalTracker,
        recovery_policy: OneShotRecoveryPolicy | None = None,
        trajectory_max_length: int = 200,
    ) -> None:
        if not expected_instance_id:
            raise ValueError("expected_instance_id is required")
        self.expected_instance_id = str(expected_instance_id)
        self.reference = reference
        self._anchor_provider = anchor_provider
        self._absolute_registrar = absolute_registrar
        self._local_tracker = local_tracker
        self._recovery = recovery_policy or OneShotRecoveryPolicy()
        self._trajectory = TrajectoryBuffer(trajectory_max_length)
        self._previous_frame: HybridFrame | None = None
        self._last_confirmed: AbsoluteRegistration | None = None
        self._pending_anchor: tuple[int, Any] | None = None
        self.mode = HybridLocalizationMode.NEED_ABSOLUTE
        self._recovery.begin()

    @property
    def recovery_revision(self) -> int:
        return self._recovery.revision

    @property
    def last_confirmed(self) -> AbsoluteRegistration | None:
        return self._last_confirmed

    def start(self) -> None:
        if self.mode is HybridLocalizationMode.STOPPED:
            self.reset()

    def stop(self) -> None:
        self._pending_anchor = None
        self.mode = HybridLocalizationMode.STOPPED

    def reset(self) -> None:
        self._previous_frame = None
        self._last_confirmed = None
        self._pending_anchor = None
        self._trajectory.reset()
        self.mode = HybridLocalizationMode.NEED_ABSOLUTE
        self._recovery.begin()

    def retry_recovery(self) -> None:
        if self.mode is not HybridLocalizationMode.RECOVERY_REQUIRED:
            raise RuntimeError("recovery retry is only valid after a failed attempt")
        self._pending_anchor = None
        self._recovery.begin()
        self.mode = HybridLocalizationMode.RECOVERY_PENDING

    def prepare_capture(self) -> HybridLocalizationState | None:
        """Read an absolute anchor before the session captures its paired frame."""
        if self.mode is HybridLocalizationMode.STOPPED:
            return self._state(reason="stopped")
        if self.mode is HybridLocalizationMode.RECOVERY_REQUIRED:
            return self._state(reason="recovery_required")
        if self.mode not in {
            HybridLocalizationMode.NEED_ABSOLUTE,
            HybridLocalizationMode.RECOVERY_PENDING,
        }:
            return None
        return self._prepare_anchor()

    def update(self, frame: HybridFrame) -> HybridLocalizationState:
        if not isinstance(frame, HybridFrame):
            raise TypeError("frame must be a HybridFrame")
        if self.mode is HybridLocalizationMode.STOPPED:
            return self._state(reason="stopped")
        if self.mode is HybridLocalizationMode.RECOVERY_REQUIRED:
            return self._state(reason="recovery_required")
        if self.mode in {
            HybridLocalizationMode.NEED_ABSOLUTE,
            HybridLocalizationMode.RECOVERY_PENDING,
        }:
            return self._attempt_absolute(frame)
        return self._track_local(frame)

    def _attempt_absolute(self, frame: HybridFrame) -> HybridLocalizationState:
        prepared = self._prepare_anchor()
        if prepared is not None:
            return prepared
        revision = self._recovery.revision
        pending = self._pending_anchor
        if pending is None or pending[0] != revision:
            self.mode = HybridLocalizationMode.RECOVERY_REQUIRED
            return self._state(reason="prepared_anchor_missing")
        self._pending_anchor = None
        anchor = pending[1]
        try:
            result = self._absolute_registrar.register(
                frame,
                reference=self.reference,
                anchor=anchor,
                prior=self._last_confirmed,
            )
        except Exception as exc:
            self.mode = HybridLocalizationMode.RECOVERY_REQUIRED
            return self._state(
                reason="absolute_registration_error",
                diagnostics={"error": str(exc), "error_type": type(exc).__name__},
            )
        if result is None:
            self.mode = HybridLocalizationMode.RECOVERY_REQUIRED
            raw_diagnostics = getattr(
                self._absolute_registrar,
                "last_diagnostics",
                {},
            )
            diagnostics = (
                dict(raw_diagnostics)
                if isinstance(raw_diagnostics, Mapping)
                else {}
            )
            return self._state(
                reason="absolute_registration_failed",
                diagnostics=diagnostics,
            )
        if result.area_instance != self.expected_instance_id:
            self.mode = HybridLocalizationMode.RECOVERY_REQUIRED
            return self._state(reason="area_instance_mismatch")
        return self._accept(frame, result)

    def _prepare_anchor(self) -> HybridLocalizationState | None:
        revision = self._recovery.revision
        pending = self._pending_anchor
        if pending is not None and pending[0] == revision:
            return None
        self._pending_anchor = None
        if not self._recovery.consume(revision):
            self.mode = HybridLocalizationMode.RECOVERY_REQUIRED
            return self._state(reason="recovery_already_consumed")
        try:
            anchor = self._anchor_provider.read_once(self.expected_instance_id)
        except Exception as exc:
            self.mode = HybridLocalizationMode.RECOVERY_REQUIRED
            return self._state(
                reason="anchor_read_failed",
                diagnostics={"error": str(exc), "error_type": type(exc).__name__},
            )
        self._pending_anchor = (revision, anchor)
        return None

    def _track_local(self, frame: HybridFrame) -> HybridLocalizationState:
        if self._previous_frame is None or self._last_confirmed is None:
            self.mode = HybridLocalizationMode.RECOVERY_PENDING
            self._recovery.begin()
            return self._state(reason="local_tracking_missing_prior")
        try:
            result = self._local_tracker.track(
                frame,
                reference=self.reference,
                previous_frame=self._previous_frame,
                previous=self._last_confirmed,
            )
        except Exception as exc:
            result = None
            diagnostics = {"error": str(exc), "error_type": type(exc).__name__}
        else:
            diagnostics = {}
        if result is None or result.area_instance != self.expected_instance_id:
            self.mode = HybridLocalizationMode.RECOVERY_PENDING
            self._recovery.begin()
            reason = "local_tracking_failed" if result is None else "area_instance_mismatch"
            return self._state(reason=reason, diagnostics=diagnostics)
        return self._accept(frame, result)

    def _accept(
        self,
        frame: HybridFrame,
        registration: AbsoluteRegistration,
    ) -> HybridLocalizationState:
        position = registration.result.position
        if position is None:
            raise ValueError("accepted registration must contain a position")
        self.mode = HybridLocalizationMode.LOCAL_TRACKING
        self._previous_frame = frame
        self._last_confirmed = registration
        self._trajectory.append(
            position,
            captured_at_ms=frame.captured_at_ms,
            confidence=registration.result.confidence,
            fresh=True,
            source=registration.result.source,
        )
        return self._state(
            position=position,
            registration=registration,
            source=registration.result.source,
            confidence=registration.result.confidence,
            diagnostics=registration.diagnostics,
        )

    def _state(
        self,
        *,
        position: tuple[float, float] | None = None,
        registration: AbsoluteRegistration | None = None,
        source: str = "failed",
        confidence: float = 0.0,
        reason: str = "",
        diagnostics: Mapping[str, Any] | None = None,
    ) -> HybridLocalizationState:
        latest = (
            self._last_confirmed.result.position
            if self._last_confirmed is not None
            else None
        )
        return HybridLocalizationState(
            mode=self.mode,
            position=position,
            latest_confirmed_position=latest,
            trajectory=self._trajectory.points,
            registration=registration,
            source=source,
            confidence=confidence,
            reason=reason,
            recovery_revision=self._recovery.revision,
            diagnostics=diagnostics or {},
        )


__all__ = ["HybridLocalizationController"]
