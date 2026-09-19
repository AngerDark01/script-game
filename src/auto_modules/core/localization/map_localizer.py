"""Generic global-first map localization orchestration."""

from __future__ import annotations

from enum import StrEnum
from typing import Any, Callable

from .result import LocalizationResult


class LocalizationMode(StrEnum):
    NEED_GLOBAL = "need_global"
    LOCAL_TRACKING = "local_tracking"
    RECOVERY_REQUIRED = "recovery_required"
    STOPPED = "stopped"


class MapLocalizer:
    """Run global registration first, then bounded local tracking.

    Matching and phase-prediction algorithms are injected so this state machine
    remains independent of any game, map package, or UI runtime.
    """

    def __init__(
        self,
        *,
        global_match: Callable[[Any], Any],
        local_match: Callable[[Any, tuple[float, float]], Any],
        phase_predict: Callable[[Any, Any], tuple[float, float] | None] | None = None,
    ) -> None:
        if not callable(global_match) or not callable(local_match):
            raise TypeError("global_match and local_match must be callable")
        if phase_predict is not None and not callable(phase_predict):
            raise TypeError("phase_predict must be callable or None")
        self._global_match = global_match
        self._local_match = local_match
        self._phase_predict = phase_predict
        self.mode = LocalizationMode.NEED_GLOBAL
        self._previous_frame: Any = None
        self._position: tuple[float, float] | None = None
        self.last_result = self._failure("not_started")

    @property
    def position(self) -> tuple[float, float] | None:
        return self._position

    def update(self, frame: Any) -> LocalizationResult:
        """Process one frame according to the current localization mode."""
        if self.mode is LocalizationMode.STOPPED:
            self.last_result = self._failure("stopped")
            return self.last_result

        if self.mode in {
            LocalizationMode.NEED_GLOBAL,
            LocalizationMode.RECOVERY_REQUIRED,
        }:
            result = self._coerce_match(self._global_match(frame), source="global")
            if result is None:
                self.mode = LocalizationMode.NEED_GLOBAL
                self.last_result = self._failure("global_match_failed")
                return self.last_result
            self._accept(frame, result)
            return result

        origin = self._predict_origin(frame)
        if origin is None:
            self.mode = LocalizationMode.RECOVERY_REQUIRED
            self.last_result = self._failure("phase_prediction_failed")
            return self.last_result

        result = self._coerce_match(self._local_match(frame, origin), source="local")
        if result is None:
            self.mode = LocalizationMode.RECOVERY_REQUIRED
            self.last_result = self._failure("local_match_failed")
            return self.last_result

        self._accept(frame, result)
        return result

    def reset(self) -> None:
        self.mode = LocalizationMode.NEED_GLOBAL
        self._previous_frame = None
        self._position = None
        self.last_result = self._failure("reset")

    def stop(self) -> None:
        self.mode = LocalizationMode.STOPPED
        self._previous_frame = None
        self._position = None
        self.last_result = self._failure("stopped")

    def _predict_origin(self, frame: Any) -> tuple[float, float] | None:
        if self._phase_predict is None:
            return self._position
        predicted = self._phase_predict(self._previous_frame, frame)
        if predicted is None:
            return self._position
        if len(predicted) != 2:
            return None
        return float(predicted[0]), float(predicted[1])

    def _accept(self, frame: Any, result: LocalizationResult) -> None:
        self.mode = LocalizationMode.LOCAL_TRACKING
        self._position = result.position
        self._previous_frame = frame
        self.last_result = result

    @staticmethod
    def _coerce_match(value: Any, *, source: str) -> LocalizationResult | None:
        if value is None:
            return None
        if isinstance(value, LocalizationResult):
            if value.position is None:
                return None
            return LocalizationResult(
                position=value.position,
                confidence=float(value.confidence),
                coordinate_space=value.coordinate_space,
                source=source,
                registration_valid=value.registration_valid,
                metadata=dict(value.metadata),
            )
        try:
            position, confidence = value
            if position is None or len(position) != 2:
                return None
            return LocalizationResult(
                position=(float(position[0]), float(position[1])),
                confidence=float(confidence),
                source=source,
                registration_valid=True,
            )
        except (TypeError, ValueError, IndexError):
            return None

    @staticmethod
    def _failure(reason: str) -> LocalizationResult:
        return LocalizationResult(
            position=None,
            confidence=0.0,
            source="failed",
            registration_valid=False,
            metadata={"reason": reason},
        )
