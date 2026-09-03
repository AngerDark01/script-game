from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from core.localization.evidence import LocalizationEvidence

from .formatting import (
    distance,
    float_point_or_none,
    format_fields,
    format_value,
    registration_fields,
)
from .localization import (
    is_f2f_registration,
    record_localization_diagnostics,
    record_visual_consistency,
    track_registration_source,
)
from .log import coord_log
from .models import CoordinateRelocalizationRequest
from .navigation import record_navigation_diagnostics
from .relocalization import (
    check_active_relocalization,
    consume_relocalization_request,
    mark_relocalization_accepted,
    register_recovery_signal,
    should_request_relocalization,
)


@dataclass
class CoordinateDiagnostics:
    """Detect suspicious localization drift and write compact evidence lines."""

    raw_control_gap_threshold: float = 42.0
    raw_jump_threshold: float = 180.0
    route_deviation_threshold: float = 96.0
    target_near_margin: float = 36.0
    target_stall_ms: int = 1200
    throttle_ms: int = 1000
    recovery_enabled: bool = True
    recovery_score_threshold: int = 3
    recovery_window_ms: int = 2600
    recovery_cooldown_ms: int = 4500
    recovery_timeout_ms: int = 2600
    long_f2f_tracking_ms: int = 8000
    visual_mismatch_threshold: float = 24.0
    visual_mismatch_required_frames: int = 3
    localization_sample_interval_ms: int = 500
    recovery_primary_signals: tuple[str, ...] = ("visual_mismatch", "raw_jump")
    _last_log_ms: dict[str, int] = field(default_factory=dict)
    _near_target_since_ms: dict[str, int] = field(default_factory=dict)
    _last_localization_sample_ms: int = 0
    _visual_mismatch_count: int = 0
    _visual_mismatch_since_ms: int = 0
    _last_raw_pos: tuple[float, float] | None = None
    _signals: list[tuple[int, str, int]] = field(default_factory=list)
    _pending_request: CoordinateRelocalizationRequest | None = None
    _active_request: CoordinateRelocalizationRequest | None = None
    _last_request_ms: int = 0
    _last_absolute_ms: int = 0
    _f2f_started_ms: int = 0

    def reset(self) -> None:
        self._last_log_ms.clear()
        self._near_target_since_ms.clear()
        self._last_localization_sample_ms = 0
        self._visual_mismatch_count = 0
        self._visual_mismatch_since_ms = 0
        self._last_raw_pos = None
        self._signals.clear()
        self._pending_request = None
        self._active_request = None
        self._last_request_ms = 0
        self._last_absolute_ms = 0
        self._f2f_started_ms = 0

    def record_session_start(self) -> None:
        coord_log(
            "coordinate diagnostics active",
            raw_control_gap_threshold=self.raw_control_gap_threshold,
            raw_jump_threshold=self.raw_jump_threshold,
            route_deviation_threshold=self.route_deviation_threshold,
            target_near_margin=self.target_near_margin,
            target_stall_ms=self.target_stall_ms,
            recovery_score_threshold=self.recovery_score_threshold,
            recovery_window_ms=self.recovery_window_ms,
            recovery_cooldown_ms=self.recovery_cooldown_ms,
            recovery_primary_signals=self.recovery_primary_signals,
            visual_mismatch_threshold=self.visual_mismatch_threshold,
            visual_mismatch_required_frames=self.visual_mismatch_required_frames,
            localization_sample_interval_ms=self.localization_sample_interval_ms,
        )

    def record_localization(
        self,
        *,
        now_ms: int,
        raw_pos,
        confidence: float,
        min_confidence: float,
        registration,
        trusted_pos,
        control_pos,
        active_task_id: str | None,
    ) -> None:
        return record_localization_diagnostics(
            self,
            now_ms=now_ms,
            raw_pos=raw_pos,
            confidence=confidence,
            min_confidence=min_confidence,
            registration=registration,
            trusted_pos=trusted_pos,
            control_pos=control_pos,
            active_task_id=active_task_id,
        )

    def record_navigation_state(
        self,
        *,
        now_ms: int,
        task_id: str | None,
        task_kind: str | None,
        target_pos,
        raw_pos,
        trusted_pos,
        control_pos,
        confidence: float,
        route_context,
        arrival_radius: float,
        registration,
    ) -> None:
        return record_navigation_diagnostics(
            self,
            now_ms=now_ms,
            task_id=task_id,
            task_kind=task_kind,
            target_pos=target_pos,
            raw_pos=raw_pos,
            trusted_pos=trusted_pos,
            control_pos=control_pos,
            confidence=confidence,
            route_context=route_context,
            arrival_radius=arrival_radius,
            registration=registration,
        )

    def consume_relocalization_request(self) -> CoordinateRelocalizationRequest | None:
        return consume_relocalization_request(self)

    def mark_relocalization_accepted(
        self,
        *,
        now_ms: int,
        pos,
        confidence: float,
        registration,
    ) -> None:
        return mark_relocalization_accepted(
            self,
            now_ms=now_ms,
            pos=pos,
            confidence=confidence,
            registration=registration,
        )

    def _log_throttled(self, message: str, now_ms: int, *, key: str, **fields: Any) -> None:
        last = self._last_log_ms.get(key, 0)
        if last and int(now_ms) - last < self.throttle_ms:
            return
        self._last_log_ms[key] = int(now_ms)
        coord_log(message, **fields)

    def _track_registration_source(self, now_ms: int, reg_fields) -> None:
        return track_registration_source(self, now_ms, reg_fields)

    def _check_active_relocalization(
        self,
        *,
        now_ms: int,
        raw: tuple[float, float] | None,
        confidence: float,
        min_confidence: float,
        reg_fields: dict[str, Any] | None = None,
        evidence: LocalizationEvidence | None = None,
    ) -> None:
        return check_active_relocalization(
            self,
            now_ms=now_ms,
            raw=raw,
            confidence=confidence,
            min_confidence=min_confidence,
            reg_fields=reg_fields,
            evidence=evidence,
        )

    def _record_visual_consistency(
        self,
        *,
        now_ms: int,
        active_task_id: str | None,
        confidence: float | None = None,
        reg_fields: dict[str, Any] | None = None,
        evidence: LocalizationEvidence | None = None,
    ) -> None:
        return record_visual_consistency(
            self,
            now_ms=now_ms,
            confidence=confidence,
            active_task_id=active_task_id,
            reg_fields=reg_fields,
            evidence=evidence,
        )

    def _register_recovery_signal(
        self,
        name: str,
        now_ms: int,
        *,
        severity: int = 1,
        **fields: Any,
    ) -> None:
        return register_recovery_signal(self, name, now_ms, severity=severity, **fields)

    def _should_request_relocalization(
        self,
        unique_scores: dict[str, int],
        score: int,
    ) -> tuple[bool, str]:
        return should_request_relocalization(self, unique_scores, score)

    def _is_f2f(self, reg_fields) -> bool:
        return is_f2f_registration(reg_fields)


def _registration_fields(registration) -> dict[str, Any]:
    return registration_fields(registration)


def _float_point_or_none(point) -> tuple[float, float] | None:
    return float_point_or_none(point)


def _distance(a: tuple[float, float], b: tuple[float, float]) -> float:
    return distance(a, b)


def _format_fields(fields: dict[str, Any]) -> str:
    return format_fields(fields)


def _format_value(value: Any) -> str:
    return format_value(value)
