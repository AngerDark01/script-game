from __future__ import annotations

from typing import Iterable

import numpy as np

from ..models import TargetDetection


def fuse_candidates(candidates: Iterable[TargetDetection], merge_radius: float) -> tuple[TargetDetection, ...]:
    """Merge nearby same-target candidates while retaining all evidence."""
    fused: list[TargetDetection] = []
    radius = max(0.0, float(merge_radius))
    for candidate in sorted(tuple(candidates), key=lambda item: item.confidence, reverse=True):
        match_index = _find_match(fused, candidate, radius)
        if match_index is None:
            fused.append(candidate)
        else:
            fused[match_index] = _merge_pair(fused[match_index], candidate)
    return tuple(fused)


def _find_match(existing: list[TargetDetection], candidate: TargetDetection, merge_radius: float) -> int | None:
    for index, item in enumerate(existing):
        if item.target_type != candidate.target_type or item.coordinate_space != candidate.coordinate_space:
            continue
        distance = float(np.hypot(item.center[0] - candidate.center[0], item.center[1] - candidate.center[1]))
        if distance <= merge_radius:
            return index
    return None


def _merge_pair(first: TargetDetection, second: TargetDetection) -> TargetDetection:
    primary, secondary = (first, second) if first.confidence >= second.confidence else (second, first)
    metadata = dict(primary.metadata)
    metadata["fused_sources"] = sorted(
        {*(metadata.get("fused_sources", [])), first.source, second.source} - {""}
    )
    return TargetDetection(
        target_type=primary.target_type,
        center=primary.center,
        coordinate_space=primary.coordinate_space,
        confidence=primary.confidence,
        bbox=primary.bbox,
        target_name=primary.target_name or secondary.target_name,
        state=primary.state,
        source="fused",
        detected_at_ms=primary.detected_at_ms or secondary.detected_at_ms,
        text=primary.text or secondary.text,
        evidence=tuple(first.evidence) + tuple(second.evidence),
        metadata=metadata,
    )
