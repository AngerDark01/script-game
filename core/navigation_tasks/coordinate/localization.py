from __future__ import annotations

from typing import Any

from core.localization.evidence import LocalizationEvidence, build_localization_evidence
from core.localization.evidence.builder import visual_check_from_metadata

from .formatting import distance
from .log import coord_log


def record_localization_diagnostics(
    diagnostics,
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
    evidence = build_localization_evidence(
        raw_pos=raw_pos,
        confidence=confidence,
        min_confidence=min_confidence,
        registration=registration,
        trusted_pos=trusted_pos,
        control_pos=control_pos,
    )
    record_localization_evidence(
        diagnostics,
        now_ms=now_ms,
        evidence=evidence,
        active_task_id=active_task_id,
    )


def record_localization_evidence(
    diagnostics,
    *,
    now_ms: int,
    evidence: LocalizationEvidence,
    active_task_id: str | None,
) -> None:
    raw = evidence.raw_pos
    trusted = evidence.trusted_pos
    control = evidence.control_pos
    conf = evidence.confidence
    reg_fields = evidence.registration_fields
    _record_localization_sample(
        diagnostics,
        now_ms=now_ms,
        evidence=evidence,
        active_task_id=active_task_id,
    )
    diagnostics._track_registration_source(now_ms, evidence)
    diagnostics._check_active_relocalization(
        now_ms=now_ms,
        raw=raw,
        confidence=conf,
        min_confidence=evidence.min_confidence,
        evidence=evidence,
    )

    reason = evidence.invalid_reason
    if reason:
        diagnostics._log_throttled(
            "localization invalid",
            now_ms,
            key=f"invalid:{reason}:{evidence.registration_source}",
            reason=reason,
            confidence=conf,
            min_confidence=evidence.min_confidence,
            active_task=active_task_id,
            trusted=trusted,
            control=control,
            **reg_fields,
        )
        return

    if diagnostics._last_raw_pos is not None:
        jump = distance(raw, diagnostics._last_raw_pos)
        if jump >= diagnostics.raw_jump_threshold:
            diagnostics._log_throttled(
                "raw localization jump",
                now_ms,
                key="raw_jump",
                raw=raw,
                previous_raw=diagnostics._last_raw_pos,
                jump=jump,
                confidence=conf,
                active_task=active_task_id,
                recommend="check_or_force_global_rematch",
                **reg_fields,
            )
            if diagnostics._is_f2f(evidence):
                diagnostics._register_recovery_signal(
                    "raw_jump",
                    now_ms,
                    severity=3,
                    raw=raw,
                    previous_raw=diagnostics._last_raw_pos,
                    jump=jump,
                    confidence=conf,
                    active_task=active_task_id,
                    **reg_fields,
                )
    diagnostics._last_raw_pos = raw

    if control is not None:
        gap = distance(raw, control)
        if gap >= diagnostics.raw_control_gap_threshold:
            diagnostics._log_throttled(
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
    diagnostics._record_visual_consistency(
        now_ms=now_ms,
        active_task_id=active_task_id,
        evidence=evidence,
    )

    if diagnostics._is_f2f(evidence) and diagnostics._f2f_started_ms:
        f2f_age = int(now_ms) - int(diagnostics._f2f_started_ms)
        if f2f_age >= diagnostics.long_f2f_tracking_ms:
            diagnostics._log_throttled(
                "long f2f tracking",
                now_ms,
                key="long_f2f_tracking",
                f2f_age_ms=f2f_age,
                confidence=conf,
                active_task=active_task_id,
                recommend="visual_check_or_periodic_global_match_if_needed",
                **reg_fields,
            )


def _record_localization_sample(
    diagnostics,
    *,
    now_ms: int,
    evidence: LocalizationEvidence,
    active_task_id: str | None,
) -> None:
    interval = int(getattr(diagnostics, "localization_sample_interval_ms", 0) or 0)
    if interval <= 0:
        return
    last = int(getattr(diagnostics, "_last_localization_sample_ms", 0) or 0)
    if last and int(now_ms) - last < interval:
        return
    diagnostics._last_localization_sample_ms = int(now_ms)

    metadata = evidence.registration_metadata or {}
    meta_keys = (
        "shift",
        "shift_dist",
        "visual_delta_dist",
        "visual_conf",
        "visual_mismatch",
        "template_top_left",
        "search_offset",
        "forced_global",
        "forced_reason",
    )
    sampled_meta = {key: metadata.get(key) for key in meta_keys if key in metadata}
    coord_log(
        "localization sample",
        raw=evidence.raw_pos,
        trusted=evidence.trusted_pos,
        control=evidence.control_pos,
        confidence=evidence.confidence,
        min_confidence=evidence.min_confidence,
        invalid_reason=evidence.invalid_reason,
        active_task=active_task_id,
        reg_valid=evidence.registration_valid,
        reg_source=evidence.registration_source,
        reg_conf=evidence.registration_confidence,
        reg_player=evidence.registration_player,
        reg_local=evidence.registration_local,
        reg_origin=evidence.registration_origin,
        reg_meta=sampled_meta,
    )


def track_registration_source(diagnostics, now_ms: int, evidence_or_fields: LocalizationEvidence | dict[str, Any]) -> None:
    if isinstance(evidence_or_fields, LocalizationEvidence):
        source = str(evidence_or_fields.registration_source or "")
        valid = bool(evidence_or_fields.registration_valid)
    else:
        source = str(evidence_or_fields.get("reg_source") or "")
        valid = bool(evidence_or_fields.get("reg_valid"))
    if valid and source == "template_match":
        diagnostics._last_absolute_ms = int(now_ms)
        diagnostics._f2f_started_ms = 0
        return
    if valid and source == "f2f":
        if not diagnostics._f2f_started_ms:
            diagnostics._f2f_started_ms = int(now_ms)
        return
    diagnostics._f2f_started_ms = 0


def record_visual_consistency(
    diagnostics,
    *,
    now_ms: int,
    active_task_id: str | None,
    evidence: LocalizationEvidence | None = None,
    reg_fields: dict[str, Any] | None = None,
    confidence: float | None = None,
) -> None:
    if evidence is None:
        evidence = _evidence_from_fields(reg_fields or {}, confidence=confidence)
    reg_fields = evidence.registration_fields
    if not diagnostics._is_f2f(evidence):
        return
    visual = evidence.visual
    if not visual.ok:
        return

    visual_delta_dist = visual.delta_dist
    visual_conf = visual.confidence
    visual_mismatch = visual.exceeds_mismatch_threshold(diagnostics.visual_mismatch_threshold)
    if not visual_mismatch:
        if diagnostics._visual_mismatch_count:
            diagnostics._log_throttled(
                "visual coordinate mismatch cleared",
                now_ms,
                key="visual_mismatch_cleared",
                count=diagnostics._visual_mismatch_count,
                visual_delta_dist=visual_delta_dist,
                visual_conf=visual_conf,
                active_task=active_task_id,
                **reg_fields,
            )
        diagnostics._visual_mismatch_count = 0
        diagnostics._visual_mismatch_since_ms = 0
        return

    if diagnostics._visual_mismatch_count <= 0:
        diagnostics._visual_mismatch_since_ms = int(now_ms)
    diagnostics._visual_mismatch_count += 1
    diagnostics._log_throttled(
        "visual coordinate mismatch",
        now_ms,
        key="visual_mismatch",
        count=diagnostics._visual_mismatch_count,
        required_frames=diagnostics.visual_mismatch_required_frames,
        visual_player=visual.player,
        visual_delta=visual.delta,
        visual_delta_dist=visual_delta_dist,
        visual_conf=visual_conf,
        visual_expected_score=visual.expected_score,
        confidence=evidence.confidence,
        active_task=active_task_id,
        **reg_fields,
    )
    if diagnostics._visual_mismatch_count >= int(diagnostics.visual_mismatch_required_frames):
        diagnostics._register_recovery_signal(
            "visual_mismatch",
            now_ms,
            severity=3,
            count=diagnostics._visual_mismatch_count,
            since_ms=diagnostics._visual_mismatch_since_ms,
            visual_player=visual.player,
            visual_delta=visual.delta,
            visual_delta_dist=visual_delta_dist,
            visual_conf=visual_conf,
            visual_expected_score=visual.expected_score,
            confidence=evidence.confidence,
            active_task=active_task_id,
            **reg_fields,
        )


def is_f2f_registration(evidence_or_fields: LocalizationEvidence | dict[str, Any]) -> bool:
    if isinstance(evidence_or_fields, LocalizationEvidence):
        return evidence_or_fields.is_f2f
    return bool(evidence_or_fields.get("reg_valid")) and str(evidence_or_fields.get("reg_source") or "") == "f2f"


def _evidence_from_fields(
    reg_fields: dict[str, Any],
    *,
    confidence: float | None = None,
) -> LocalizationEvidence:
    metadata = dict(reg_fields.get("reg_meta") or {})
    return LocalizationEvidence(
        raw_pos=None,
        trusted_pos=None,
        control_pos=None,
        confidence=float(confidence or 0.0),
        min_confidence=0.0,
        registration_present=bool(reg_fields),
        registration_valid=reg_fields.get("reg_valid"),
        registration_source=reg_fields.get("reg_source"),
        registration_confidence=float(reg_fields.get("reg_conf") or 0.0),
        registration_player=reg_fields.get("reg_player"),
        registration_local=reg_fields.get("reg_local"),
        registration_origin=reg_fields.get("reg_origin"),
        registration_metadata=metadata,
        visual=visual_check_from_metadata(metadata),
    )
