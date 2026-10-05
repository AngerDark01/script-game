"""Adapters from the shared PoE2 observation contract to dual candidates."""

from __future__ import annotations

import math
from typing import Any

import cv2
import numpy as np

from auto_modules.core.localization.observations import (
    ObservationCandidate,
    ObservationFrame,
)

from .models import MarkerColorProfile, PlayerMarkerCandidate


def _same_marker_component(
    first: ObservationCandidate,
    second: ObservationCandidate,
) -> bool:
    """Return whether two contours are likely the same minimap marker.

    The color detector can expose an outline and a filled core as separate
    contours.  They should count as one player, while two nearby players must
    remain separate.  Only use geometry when both contours provide a bbox;
    synthetic/other providers without geometry keep their previous behavior.
    """
    first_evidence = getattr(first, "evidence", {}) or {}
    second_evidence = getattr(second, "evidence", {}) or {}
    # Configured color profiles are identity evidence. Two different player
    # colors may overlap in the minimap when the characters stand together;
    # never collapse those contours as an outline/core duplicate.
    first_profile = first_evidence.get("profile_index")
    second_profile = second_evidence.get("profile_index")
    if first_profile is not None and second_profile is not None and first_profile != second_profile:
        return False
    first_hint = getattr(first, "identity_hint", None)
    second_hint = getattr(second, "identity_hint", None)
    if first_hint and second_hint and first_hint != second_hint and first_profile is None and second_profile is None:
        return False
    first_box = first_evidence.get("bbox")
    second_box = second_evidence.get("bbox")
    if not (
        isinstance(first_box, (tuple, list))
        and isinstance(second_box, (tuple, list))
        and len(first_box) == 4
        and len(second_box) == 4
    ):
        return False
    x1, y1, w1, h1 = (float(value) for value in first_box)
    x2, y2, w2, h2 = (float(value) for value in second_box)
    if min(w1, h1, w2, h2) <= 0.0:
        return False
    left = max(x1, x2)
    top = max(y1, y2)
    right = min(x1 + w1, x2 + w2)
    bottom = min(y1 + h1, y2 + h2)
    intersection = max(0.0, right - left) * max(0.0, bottom - top)
    union = w1 * h1 + w2 * h2 - intersection
    iou = intersection / union if union > 0.0 else 0.0
    center_distance = math.dist(first.local_position, second.local_position)
    diameter = max(w1, h1, w2, h2)
    return iou >= 0.35 or center_distance <= max(1.5, diameter * 0.55)


def _deduplicate_marker_contours(
    ranked: list[tuple[int, ObservationCandidate]],
) -> list[tuple[int, ObservationCandidate]]:
    """Apply confidence-ordered geometric NMS to contour/core duplicates."""
    kept: list[tuple[int, ObservationCandidate]] = []
    for item in ranked:
        candidate = item[1]
        if any(_same_marker_component(candidate, existing) for _, existing in kept):
            continue
        kept.append(item)
    return kept


def marker_candidates_from_observation(
    observation: ObservationFrame,
    *,
    max_candidates: int = 2,
) -> tuple[PlayerMarkerCandidate, ...]:
    """Convert the two best-quality observations without assigning identity.

    Sorting here only removes extra noise components.  The dual registrar still
    evaluates both candidate-to-memory permutations and never treats ordering
    as player identity.
    """
    if not isinstance(observation, ObservationFrame):
        raise TypeError("observation must be an ObservationFrame")
    limit = int(max_candidates)
    if limit < 1:
        raise ValueError("max_candidates must be positive")
    ranked_all = sorted(
        enumerate(observation.candidates),
        key=lambda item: float(item[1].confidence),
        reverse=True,
    )
    ranked_all = _deduplicate_marker_contours(ranked_all)
    # A bright marker can produce more than one contour (outline + core) for
    # the same player.  Taking the global top two then drops the other player
    # intermittently, especially when the two characters are close.  Reserve
    # one candidate for each configured profile/identity hint first; the
    # registrar still validates the final assignment against memory anchors.
    ranked: list[tuple[int, ObservationCandidate]] = []
    seen_groups: set[str] = set()
    for item in ranked_all:
        candidate = item[1]
        evidence = getattr(candidate, "evidence", {}) or {}
        group_value = evidence.get("profile_index")
        if group_value is None:
            group_value = candidate.identity_hint
        group = str(group_value or "")
        if not group or group in seen_groups:
            continue
        ranked.append(item)
        seen_groups.add(group)
        if len(ranked) >= limit:
            break
    if len(ranked) < limit:
        selected = {index for index, _ in ranked}
        ranked.extend(item for item in ranked_all if item[0] not in selected)
        ranked = ranked[:limit]
    result: list[PlayerMarkerCandidate] = []
    for index, candidate in ranked:
        evidence: dict[str, Any] = dict(candidate.evidence)
        area = float(evidence.get("area", 0.0) or 0.0)
        bbox = evidence.get("bbox")
        result.append(
            PlayerMarkerCandidate(
                candidate_id=f"observation-{index}",
                local_position=candidate.local_position,
                confidence=candidate.confidence,
                area=area,
                bbox=tuple(bbox) if isinstance(bbox, (tuple, list)) and len(bbox) == 4 else None,
                color_features={
                    "identity_hint": candidate.identity_hint,
                    **evidence,
                },
            )
        )
    return tuple(result)


__all__ = ["marker_candidates_from_observation"]


def detect_saturated_marker_observation(
    image: Any,
    captured_at_ms: int,
    *,
    min_area: float = 8.0,
    max_area: float = 55.0,
    max_dimension: int = 14,
    saturation_threshold: int = 150,
    value_threshold: int = 150,
    profiles: tuple[MarkerColorProfile, ...] | list[MarkerColorProfile] | None = None,
) -> ObservationFrame:
    """Extract compact colored marker candidates without a center prior.

    This is intentionally an experimental detector.  It treats compact,
    saturated components as candidates and leaves identity and map validation
    to the dual anchor registrar.  Large colored terrain/label components are
    filtered by area and bounding-box dimensions, while the complete raw mask
    remains available in diagnostics for later tuning.
    """
    array = np.asarray(image)
    if array.ndim != 3 or array.shape[2] < 3 or array.size == 0:
        raise ValueError("image must be a non-empty BGR color image")
    if float(min_area) < 0 or float(max_area) < float(min_area):
        raise ValueError("marker area bounds are invalid")
    if int(max_dimension) < 1:
        raise ValueError("max_dimension must be positive")
    hsv = cv2.cvtColor(array[:, :, :3], cv2.COLOR_BGR2HSV)
    configured = tuple(profile for profile in (profiles or ()) if profile.enabled)
    if profiles is not None and not configured:
        return ObservationFrame(
            captured_at_ms=int(captured_at_ms),
            candidates=(),
            source="configured-color-marker",
        )
    profile_masks: list[tuple[str, np.ndarray, float, float, int, int]] = []
    if configured:
        for profile in configured:
            if profile.hue_min <= profile.hue_max:
                hue_mask = cv2.inRange(
                    hsv,
                    np.array([profile.hue_min, profile.saturation_min, profile.value_min], dtype=np.uint8),
                    np.array([profile.hue_max, 255, 255], dtype=np.uint8),
                )
            else:
                low = cv2.inRange(
                    hsv,
                    np.array([0, profile.saturation_min, profile.value_min], dtype=np.uint8),
                    np.array([profile.hue_max, 255, 255], dtype=np.uint8),
                )
                high = cv2.inRange(
                    hsv,
                    np.array([profile.hue_min, profile.saturation_min, profile.value_min], dtype=np.uint8),
                    np.array([179, 255, 255], dtype=np.uint8),
                )
                hue_mask = cv2.bitwise_or(low, high)
            profile_masks.append(
                (
                    profile.name,
                    hue_mask,
                    profile.min_area,
                    profile.max_area,
                    profile.max_dimension,
                    profile.saturation_min,
                )
            )
    else:
        profile_masks.append(
            (
                "saturated",
                cv2.inRange(
                    hsv,
                    np.array([0, int(saturation_threshold), int(value_threshold)], dtype=np.uint8),
                    np.array([179, 255, 255], dtype=np.uint8),
                ),
                float(min_area),
                float(max_area),
                int(max_dimension),
                int(saturation_threshold),
            )
        )
    candidates: list[ObservationCandidate] = []
    rejected = 0
    for profile_index, (profile_name, mask, profile_min_area, profile_max_area, profile_max_dim, _sat) in enumerate(profile_masks):
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        for contour in contours:
            area = float(cv2.contourArea(contour))
            x, y, width, height = (int(value) for value in cv2.boundingRect(contour))
            if (
                area < profile_min_area
                or area > profile_max_area
                or width > profile_max_dim
                or height > profile_max_dim
                or x <= 0
                or y <= 0
                or x + width >= array.shape[1]
                or y + height >= array.shape[0]
            ):
                rejected += 1
                continue
            moments = cv2.moments(contour)
            if moments["m00"] <= 0:
                rejected += 1
                continue
            position = (float(moments["m10"] / moments["m00"]), float(moments["m01"] / moments["m00"]))
            compactness = min(1.0, area / max(1.0, float(width * height)))
            confidence = min(0.99, 0.55 + min(area, 45.0) / 100.0 + compactness * 0.10)
            contour_mask = np.zeros(mask.shape, dtype=np.uint8)
            cv2.drawContours(contour_mask, [contour], -1, 255, thickness=-1)
            hue_values = hsv[:, :, 0][contour_mask > 0]
            candidates.append(
                ObservationCandidate(
                    (int(round(position[0])), int(round(position[1]))),
                    confidence,
                    identity_hint=profile_name if configured else "poe2-saturated-marker",
                    evidence={
                        "area": area,
                        "bbox": [x, y, width, height],
                        "compactness": compactness,
                        "hue": float(np.median(hue_values)) if hue_values.size else None,
                        "detector": "configured_components" if configured else "saturated_components",
                        "profile": profile_name if configured else None,
                        "profile_index": profile_index if configured else None,
                    },
                )
            )
    candidates.sort(key=lambda candidate: candidate.confidence, reverse=True)
    return ObservationFrame(
        captured_at_ms=int(captured_at_ms),
        candidates=tuple(candidates),
        source="configured-color-marker" if configured else "saturated-color-marker-experiment",
    )


__all__ = [
    "detect_saturated_marker_observation",
    "marker_candidates_from_observation",
]
