from __future__ import annotations

import math
import os
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any


_COORD_LOG_PATH = Path(__file__).resolve().parents[2] / "logs" / "coordinate_diagnostics.log"
_COORD_SESSION_STARTED = False


def coord_log(message: str, **fields: Any) -> None:
    """Write coordinate diagnostics to a dedicated file without console spam."""
    global _COORD_SESSION_STARTED
    suffix = _format_fields(fields)
    timestamp = time.strftime("%H:%M:%S")
    millis = int((time.time() % 1) * 1000)
    line = f"[Coord {timestamp}.{millis:03d} pid={os.getpid()}] {message}{suffix}"
    _COORD_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    mode = "a" if _COORD_SESSION_STARTED else "w"
    with _COORD_LOG_PATH.open(mode, encoding="utf-8") as handle:
        if not _COORD_SESSION_STARTED:
            handle.write(f"=== coordinate diagnostics session {time.strftime('%Y-%m-%d %H:%M:%S')} ===\n")
            _COORD_SESSION_STARTED = True
        handle.write(line + "\n")


@dataclass
class CoordinateRelocalizationRequest:
    reason: str
    requested_at_ms: int
    score: int = 0
    signals: tuple[str, ...] = field(default_factory=tuple)
    details: dict[str, Any] = field(default_factory=dict)


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
    recovery_primary_signals: tuple[str, ...] = ("visual_mismatch", "raw_jump")
    _last_log_ms: dict[str, int] = field(default_factory=dict)
    _near_target_since_ms: dict[str, int] = field(default_factory=dict)
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
        raw = _float_point_or_none(raw_pos)
        trusted = _float_point_or_none(trusted_pos)
        control = _float_point_or_none(control_pos)
        conf = float(confidence or 0.0)
        reg_fields = _registration_fields(registration)
        self._track_registration_source(now_ms, reg_fields)
        self._check_active_relocalization(
            now_ms=now_ms,
            raw=raw,
            confidence=conf,
            min_confidence=float(min_confidence),
            reg_fields=reg_fields,
        )

        if raw is None or conf < float(min_confidence):
            reason = "no_position" if raw is None else "low_confidence"
            self._log_throttled(
                "localization invalid",
                now_ms,
                key=f"invalid:{reason}:{reg_fields.get('reg_source')}",
                reason=reason,
                confidence=conf,
                min_confidence=float(min_confidence),
                active_task=active_task_id,
                trusted=trusted,
                control=control,
                **reg_fields,
            )
            return

        if self._last_raw_pos is not None:
            jump = _distance(raw, self._last_raw_pos)
            if jump >= self.raw_jump_threshold:
                self._log_throttled(
                    "raw localization jump",
                    now_ms,
                    key="raw_jump",
                    raw=raw,
                    previous_raw=self._last_raw_pos,
                    jump=jump,
                    confidence=conf,
                    active_task=active_task_id,
                    recommend="check_or_force_global_rematch",
                    **reg_fields,
                )
                if self._is_f2f(reg_fields):
                    self._register_recovery_signal(
                        "raw_jump",
                        now_ms,
                        severity=3,
                        raw=raw,
                        previous_raw=self._last_raw_pos,
                        jump=jump,
                        confidence=conf,
                        active_task=active_task_id,
                        **reg_fields,
                    )
        self._last_raw_pos = raw

        if control is not None:
            gap = _distance(raw, control)
            if gap >= self.raw_control_gap_threshold:
                self._log_throttled(
                    "raw control gap",
                    now_ms,
                    key="raw_control_gap",
                    raw=raw,
                    trusted=trusted,
                    control=control,
                    gap=gap,
                    confidence=conf,
                    active_task=active_task_id,
                    recommend="diagnostic_only_visual_check_drives_relocalization",
                    **reg_fields,
                )
        self._record_visual_consistency(
            now_ms=now_ms,
            confidence=conf,
            active_task_id=active_task_id,
            reg_fields=reg_fields,
        )

        if self._is_f2f(reg_fields) and self._f2f_started_ms:
            f2f_age = int(now_ms) - int(self._f2f_started_ms)
            if f2f_age >= self.long_f2f_tracking_ms:
                self._log_throttled(
                    "long f2f tracking",
                    now_ms,
                    key="long_f2f_tracking",
                    f2f_age_ms=f2f_age,
                    confidence=conf,
                    active_task=active_task_id,
                    recommend="visual_check_or_periodic_global_match_if_needed",
                    **reg_fields,
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
        target = _float_point_or_none(target_pos)
        raw = _float_point_or_none(raw_pos)
        trusted = _float_point_or_none(trusted_pos)
        control = _float_point_or_none(control_pos)
        if target is None or control is None:
            return

        reg_fields = _registration_fields(registration)
        route_projection = route_context.project(control) if route_context is not None else None
        route_deviation = None if route_projection is None else float(route_projection.deviation)
        route_progress = None if route_projection is None else float(route_projection.progress)
        control_to_target = _distance(control, target)
        raw_to_target = None if raw is None else _distance(raw, target)
        trusted_to_target = None if trusted is None else _distance(trusted, target)
        radius = float(arrival_radius)

        if route_deviation is not None and route_deviation >= self.route_deviation_threshold:
            self._log_throttled(
                "route projection deviation",
                now_ms,
                key=f"route_deviation:{task_id}",
                task=task_id,
                kind=task_kind,
                target=target,
                raw=raw,
                trusted=trusted,
                control=control,
                confidence=float(confidence or 0.0),
                route_deviation=route_deviation,
                route_progress=route_progress,
                recommend="inspect_route_anchor_or_path_not_relocalization",
                **reg_fields,
            )

        if raw_to_target is not None and raw_to_target <= radius < control_to_target:
            self._log_throttled(
                "arrival mismatch raw inside control outside",
                now_ms,
                key=f"arrival_mismatch:{task_id}",
                task=task_id,
                kind=task_kind,
                target=target,
                raw=raw,
                trusted=trusted,
                control=control,
                raw_distance=raw_to_target,
                control_distance=control_to_target,
                trusted_distance=trusted_to_target,
                arrival_radius=radius,
                confidence=float(confidence or 0.0),
                recommend="inspect_control_smoothing_or_completion_radius",
                **reg_fields,
            )

        near_limit = radius + self.target_near_margin
        near_key = str(task_id or "unknown")
        if radius < control_to_target <= near_limit:
            since = self._near_target_since_ms.setdefault(near_key, int(now_ms))
            if int(now_ms) - since >= self.target_stall_ms:
                self._log_throttled(
                    "near target not completed",
                    now_ms,
                    key=f"near_target:{near_key}",
                    task=task_id,
                    kind=task_kind,
                    target=target,
                    raw=raw,
                    trusted=trusted,
                    control=control,
                    raw_distance=raw_to_target,
                    control_distance=control_to_target,
                    trusted_distance=trusted_to_target,
                    arrival_radius=radius,
                    near_limit=near_limit,
                    stalled_ms=int(now_ms) - since,
                    confidence=float(confidence or 0.0),
                    route_deviation=route_deviation,
                    route_progress=route_progress,
                    recommend="inspect_arrival_radius_or_movement_not_relocalization",
                    **reg_fields,
                )
        else:
            self._near_target_since_ms.pop(near_key, None)

    def consume_relocalization_request(self) -> CoordinateRelocalizationRequest | None:
        request = self._pending_request
        if request is None:
            return None
        self._pending_request = None
        self._active_request = request
        coord_log(
            "coordinate relocalization forced",
            reason=request.reason,
            score=request.score,
            signals=request.signals,
            details=request.details,
        )
        return request

    def mark_relocalization_accepted(self, *, now_ms: int, pos, confidence: float, registration) -> None:
        accepted = _float_point_or_none(pos)
        if accepted is None:
            return
        request = self._active_request
        self._active_request = None
        self._signals.clear()
        self._near_target_since_ms.clear()
        self._visual_mismatch_count = 0
        self._visual_mismatch_since_ms = 0
        self._f2f_started_ms = 0
        self._last_absolute_ms = int(now_ms)
        coord_log(
            "coordinate relocalization accepted",
            reason=request.reason if request else "external_forced_global",
            pos=accepted,
            confidence=float(confidence or 0.0),
            **_registration_fields(registration),
        )

    def _log_throttled(self, message: str, now_ms: int, *, key: str, **fields: Any) -> None:
        last = self._last_log_ms.get(key, 0)
        if last and int(now_ms) - last < self.throttle_ms:
            return
        self._last_log_ms[key] = int(now_ms)
        coord_log(message, **fields)

    def _track_registration_source(self, now_ms: int, reg_fields: dict[str, Any]) -> None:
        source = str(reg_fields.get("reg_source") or "")
        valid = bool(reg_fields.get("reg_valid"))
        if valid and source == "template_match":
            self._last_absolute_ms = int(now_ms)
            self._f2f_started_ms = 0
            return
        if valid and source == "f2f":
            if not self._f2f_started_ms:
                self._f2f_started_ms = int(now_ms)
            return
        self._f2f_started_ms = 0

    def _check_active_relocalization(
        self,
        *,
        now_ms: int,
        raw: tuple[float, float] | None,
        confidence: float,
        min_confidence: float,
        reg_fields: dict[str, Any],
    ) -> None:
        request = self._active_request
        if request is None:
            return
        metadata = reg_fields.get("reg_meta") or {}
        accepted = (
            raw is not None
            and bool(reg_fields.get("reg_valid"))
            and str(reg_fields.get("reg_source") or "") == "template_match"
            and bool(metadata.get("forced_global"))
            and float(confidence or 0.0) >= float(min_confidence)
        )
        if accepted:
            return
        if int(now_ms) - int(request.requested_at_ms) >= self.recovery_timeout_ms:
            coord_log(
                "coordinate relocalization rejected",
                reason=request.reason,
                score=request.score,
                raw=raw,
                confidence=float(confidence or 0.0),
                min_confidence=float(min_confidence),
                **reg_fields,
            )
            self._active_request = None
            self._signals.clear()
            self._near_target_since_ms.clear()
            self._visual_mismatch_count = 0
            self._visual_mismatch_since_ms = 0

    def _record_visual_consistency(
        self,
        *,
        now_ms: int,
        confidence: float,
        active_task_id: str | None,
        reg_fields: dict[str, Any],
    ) -> None:
        if not self._is_f2f(reg_fields):
            return
        metadata = reg_fields.get("reg_meta") or {}
        if metadata.get("visual_check") != "ok":
            return

        visual_delta_dist = float(metadata.get("visual_delta_dist") or 0.0)
        visual_conf = float(metadata.get("visual_conf") or 0.0)
        visual_mismatch = bool(metadata.get("visual_mismatch")) and visual_delta_dist >= float(self.visual_mismatch_threshold)
        if not visual_mismatch:
            if self._visual_mismatch_count:
                self._log_throttled(
                    "visual coordinate mismatch cleared",
                    now_ms,
                    key="visual_mismatch_cleared",
                    count=self._visual_mismatch_count,
                    visual_delta_dist=visual_delta_dist,
                    visual_conf=visual_conf,
                    active_task=active_task_id,
                    **reg_fields,
                )
            self._visual_mismatch_count = 0
            self._visual_mismatch_since_ms = 0
            return

        if self._visual_mismatch_count <= 0:
            self._visual_mismatch_since_ms = int(now_ms)
        self._visual_mismatch_count += 1
        self._log_throttled(
            "visual coordinate mismatch",
            now_ms,
            key="visual_mismatch",
            count=self._visual_mismatch_count,
            required_frames=self.visual_mismatch_required_frames,
            visual_player=metadata.get("visual_player"),
            visual_delta=metadata.get("visual_delta"),
            visual_delta_dist=visual_delta_dist,
            visual_conf=visual_conf,
            visual_expected_score=metadata.get("visual_expected_score"),
            confidence=float(confidence or 0.0),
            active_task=active_task_id,
            **reg_fields,
        )
        if self._visual_mismatch_count >= int(self.visual_mismatch_required_frames):
            self._register_recovery_signal(
                "visual_mismatch",
                now_ms,
                severity=3,
                count=self._visual_mismatch_count,
                since_ms=self._visual_mismatch_since_ms,
                visual_player=metadata.get("visual_player"),
                visual_delta=metadata.get("visual_delta"),
                visual_delta_dist=visual_delta_dist,
                visual_conf=visual_conf,
                visual_expected_score=metadata.get("visual_expected_score"),
                confidence=float(confidence or 0.0),
                active_task=active_task_id,
                **reg_fields,
            )

    def _register_recovery_signal(self, name: str, now_ms: int, *, severity: int = 1, **fields: Any) -> None:
        if not self.recovery_enabled:
            return
        if self._pending_request is not None or self._active_request is not None:
            return
        if self._last_request_ms and int(now_ms) - int(self._last_request_ms) < self.recovery_cooldown_ms:
            return

        cutoff = int(now_ms) - int(self.recovery_window_ms)
        self._signals = [(ts, sig, sev) for ts, sig, sev in self._signals if ts >= cutoff]
        self._signals.append((int(now_ms), str(name), max(0, int(severity))))
        unique_scores: dict[str, int] = {}
        for _, sig, sev in self._signals:
            unique_scores[sig] = max(unique_scores.get(sig, 0), int(sev))
        score = sum(unique_scores.values())
        if score < self.recovery_score_threshold:
            return

        signal_names = tuple(dict.fromkeys(sig for _, sig, _ in self._signals))
        should_request, suppress_reason = self._should_request_relocalization(unique_scores, score)
        if not should_request:
            self._log_throttled(
                "coordinate relocalization suppressed",
                now_ms,
                key=f"recovery_suppressed:{suppress_reason}:{'+'.join(signal_names)}",
                reason="+".join(signal_names),
                suppress_reason=suppress_reason,
                score=score,
                unique_scores=unique_scores,
                latest=str(name),
                **fields,
            )
            return
        reason = "+".join(signal_names)
        details = {
            "latest": str(name),
            "score": score,
            "window_ms": int(self.recovery_window_ms),
            "unique_scores": unique_scores,
        }
        self._pending_request = CoordinateRelocalizationRequest(
            reason=reason,
            requested_at_ms=int(now_ms),
            score=score,
            signals=signal_names,
            details=details,
        )
        self._last_request_ms = int(now_ms)
        coord_log(
            "coordinate relocalization requested",
            reason=reason,
            score=score,
            signals=signal_names,
            **fields,
        )

    def _should_request_relocalization(self, unique_scores: dict[str, int], score: int) -> tuple[bool, str]:
        signal_names = set(unique_scores)
        primary = signal_names.intersection(self.recovery_primary_signals)
        if not primary:
            return False, "no_primary_signal"
        if "raw_jump" in primary:
            return True, ""
        if "visual_mismatch" in primary:
            return True, ""
        return False, "unsupported_primary_signal"

    def _is_f2f(self, reg_fields: dict[str, Any]) -> bool:
        return bool(reg_fields.get("reg_valid")) and str(reg_fields.get("reg_source") or "") == "f2f"


def _registration_fields(registration) -> dict[str, Any]:
    if registration is None:
        return {"reg_valid": None, "reg_source": None}
    return {
        "reg_valid": bool(getattr(registration, "valid", False)),
        "reg_source": getattr(registration, "source", ""),
        "reg_conf": float(getattr(registration, "confidence", 0.0) or 0.0),
        "reg_player": _float_point_or_none(getattr(registration, "player_global_pos", None)),
        "reg_local": getattr(registration, "player_local_minimap_pos", None),
        "reg_origin": _float_point_or_none(getattr(registration, "frame_origin_global", None)),
        "reg_meta": getattr(registration, "metadata", {}) or {},
    }


def _float_point_or_none(point) -> tuple[float, float] | None:
    if point is None:
        return None
    try:
        return (float(point[0]), float(point[1]))
    except (TypeError, ValueError, IndexError):
        return None


def _distance(a: tuple[float, float], b: tuple[float, float]) -> float:
    return math.hypot(float(a[0]) - float(b[0]), float(a[1]) - float(b[1]))


def _format_fields(fields: dict[str, Any]) -> str:
    if not fields:
        return ""
    return " | " + " ".join(f"{key}={_format_value(value)}" for key, value in fields.items())


def _format_value(value: Any) -> str:
    if isinstance(value, Enum):
        return str(value.value)
    if isinstance(value, float):
        return f"{value:.2f}"
    if isinstance(value, (tuple, list)):
        return "(" + ",".join(_format_value(item) for item in value) + ")"
    if isinstance(value, dict):
        return "{" + ",".join(f"{key}:{_format_value(val)}" for key, val in value.items()) + "}"
    return str(value)
