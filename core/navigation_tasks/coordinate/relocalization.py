from __future__ import annotations

from typing import Any

from core.localization.evidence import LocalizationEvidence

from .formatting import float_point_or_none, registration_fields
from .log import coord_log
from .models import CoordinateRelocalizationRequest


def consume_relocalization_request(diagnostics) -> CoordinateRelocalizationRequest | None:
    request = diagnostics._pending_request
    if request is None:
        return None
    diagnostics._pending_request = None
    diagnostics._active_request = request
    coord_log(
        "coordinate relocalization forced",
        reason=request.reason,
        score=request.score,
        signals=request.signals,
        details=request.details,
    )
    return request


def mark_relocalization_accepted(diagnostics, *, now_ms: int, pos, confidence: float, registration) -> None:
    accepted = float_point_or_none(pos)
    if accepted is None:
        return
    request = diagnostics._active_request
    diagnostics._active_request = None
    diagnostics._signals.clear()
    diagnostics._near_target_since_ms.clear()
    diagnostics._visual_mismatch_count = 0
    diagnostics._visual_mismatch_since_ms = 0
    diagnostics._f2f_started_ms = 0
    diagnostics._last_absolute_ms = int(now_ms)
    coord_log(
        "coordinate relocalization accepted",
        reason=request.reason if request else "external_forced_global",
        pos=accepted,
        confidence=float(confidence or 0.0),
        **registration_fields(registration),
    )


def check_active_relocalization(
    diagnostics,
    *,
    now_ms: int,
    raw: tuple[float, float] | None,
    confidence: float,
    min_confidence: float,
    reg_fields: dict[str, Any] | None = None,
    evidence: LocalizationEvidence | None = None,
) -> None:
    request = diagnostics._active_request
    if request is None:
        return
    if evidence is not None:
        reg_fields = evidence.registration_fields
        metadata = evidence.registration_metadata
        accepted = (
            evidence.raw_pos is not None
            and evidence.is_template_match
            and evidence.forced_global
            and evidence.confidence >= float(min_confidence)
        )
    else:
        reg_fields = reg_fields or {}
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
    if int(now_ms) - int(request.requested_at_ms) >= diagnostics.recovery_timeout_ms:
        coord_log(
            "coordinate relocalization rejected",
            reason=request.reason,
            score=request.score,
            raw=raw,
            confidence=float(confidence or 0.0),
            min_confidence=float(min_confidence),
            **reg_fields,
        )
        diagnostics._active_request = None
        diagnostics._signals.clear()
        diagnostics._near_target_since_ms.clear()
        diagnostics._visual_mismatch_count = 0
        diagnostics._visual_mismatch_since_ms = 0


def register_recovery_signal(diagnostics, name: str, now_ms: int, *, severity: int = 1, **fields: Any) -> None:
    if not diagnostics.recovery_enabled:
        return
    if diagnostics._pending_request is not None or diagnostics._active_request is not None:
        return
    if diagnostics._last_request_ms and int(now_ms) - int(diagnostics._last_request_ms) < diagnostics.recovery_cooldown_ms:
        return

    cutoff = int(now_ms) - int(diagnostics.recovery_window_ms)
    diagnostics._signals = [(ts, sig, sev) for ts, sig, sev in diagnostics._signals if ts >= cutoff]
    diagnostics._signals.append((int(now_ms), str(name), max(0, int(severity))))
    unique_scores: dict[str, int] = {}
    for _, sig, sev in diagnostics._signals:
        unique_scores[sig] = max(unique_scores.get(sig, 0), int(sev))
    score = sum(unique_scores.values())
    if score < diagnostics.recovery_score_threshold:
        return

    signal_names = tuple(dict.fromkeys(sig for _, sig, _ in diagnostics._signals))
    should_request, suppress_reason = diagnostics._should_request_relocalization(unique_scores, score)
    if not should_request:
        diagnostics._log_throttled(
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
        "window_ms": int(diagnostics.recovery_window_ms),
        "unique_scores": unique_scores,
    }
    diagnostics._pending_request = CoordinateRelocalizationRequest(
        reason=reason,
        requested_at_ms=int(now_ms),
        score=score,
        signals=signal_names,
        details=details,
    )
    diagnostics._last_request_ms = int(now_ms)
    coord_log(
        "coordinate relocalization requested",
        reason=reason,
        score=score,
        signals=signal_names,
        **fields,
    )


def should_request_relocalization(diagnostics, unique_scores: dict[str, int], score: int) -> tuple[bool, str]:
    signal_names = set(unique_scores)
    primary = signal_names.intersection(diagnostics.recovery_primary_signals)
    if not primary:
        return False, "no_primary_signal"
    if "raw_jump" in primary:
        return True, ""
    if "visual_mismatch" in primary:
        return True, ""
    return False, "unsupported_primary_signal"
