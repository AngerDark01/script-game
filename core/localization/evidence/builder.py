from __future__ import annotations

from typing import Any

from .models import LocalizationEvidence, VisualCheckEvidence


def build_localization_evidence(
    *,
    raw_pos,
    confidence: float,
    min_confidence: float,
    registration,
    trusted_pos,
    control_pos,
) -> LocalizationEvidence:
    metadata = getattr(registration, "metadata", {}) or {}
    return LocalizationEvidence(
        raw_pos=float_point_or_none(raw_pos),
        trusted_pos=float_point_or_none(trusted_pos),
        control_pos=float_point_or_none(control_pos),
        confidence=float(confidence or 0.0),
        min_confidence=float(min_confidence),
        registration_present=registration is not None,
        registration_valid=None if registration is None else bool(getattr(registration, "valid", False)),
        registration_source=None if registration is None else getattr(registration, "source", ""),
        registration_confidence=float(getattr(registration, "confidence", 0.0) or 0.0),
        registration_player=float_point_or_none(getattr(registration, "player_global_pos", None)),
        registration_local=getattr(registration, "player_local_minimap_pos", None),
        registration_origin=float_point_or_none(getattr(registration, "frame_origin_global", None)),
        registration_metadata=dict(metadata),
        visual=visual_check_from_metadata(metadata),
    )


def registration_fields_from_registration(registration) -> dict[str, Any]:
    return build_localization_evidence(
        raw_pos=None,
        confidence=0.0,
        min_confidence=0.0,
        registration=registration,
        trusted_pos=None,
        control_pos=None,
    ).registration_fields


def visual_check_from_metadata(metadata: dict[str, Any]) -> VisualCheckEvidence:
    return VisualCheckEvidence(
        status=str(metadata.get("visual_check") or ""),
        player=metadata.get("visual_player"),
        delta=metadata.get("visual_delta"),
        delta_dist=float(metadata.get("visual_delta_dist") or 0.0),
        confidence=float(metadata.get("visual_conf") or 0.0),
        expected_score=metadata.get("visual_expected_score"),
        mismatch=bool(metadata.get("visual_mismatch")),
    )


def float_point_or_none(point) -> tuple[float, float] | None:
    if point is None:
        return None
    try:
        return (float(point[0]), float(point[1]))
    except (TypeError, ValueError, IndexError):
        return None
