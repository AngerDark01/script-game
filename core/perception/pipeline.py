from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

import numpy as np

from .models import TargetDetection
from .profiles import TargetProfile
from .registry import AlgorithmRegistry


@dataclass(frozen=True)
class PerceptionRunResult:
    """Raw per-algorithm output plus spatially fused target candidates."""

    detections: tuple[TargetDetection, ...]
    by_algorithm: Mapping[str, tuple[TargetDetection, ...]] = field(default_factory=dict)
    errors: Mapping[str, str] = field(default_factory=dict)


class PerceptionPipeline:
    """Run the algorithm instances selected by one target profile."""

    def __init__(self, registry: AlgorithmRegistry) -> None:
        self.registry = registry

    def run(self, frame: Any, profile: TargetProfile) -> PerceptionRunResult:
        by_algorithm: dict[str, tuple[TargetDetection, ...]] = {}
        errors: dict[str, str] = {}
        candidates: list[TargetDetection] = []
        for algorithm_profile in profile.algorithms:
            if not algorithm_profile.enabled:
                continue
            try:
                parameters = dict(algorithm_profile.parameters)
                parameters.setdefault("target_type", profile.target_type)
                detector = self.registry.create(algorithm_profile.algorithm_id, parameters)
                detected = tuple(detector.detect(frame) or ())
            except Exception as exc:
                errors[algorithm_profile.instance_id] = f"{type(exc).__name__}: {exc}"
                continue
            by_algorithm[algorithm_profile.instance_id] = detected
            candidates.extend(
                item for item in detected if float(item.confidence) >= float(profile.min_confidence)
            )

        merge_radius = max(0.0, float(profile.metadata.get("merge_radius", 12.0)))
        fused = tuple(_fuse_candidates(candidates, merge_radius))
        return PerceptionRunResult(detections=fused, by_algorithm=by_algorithm, errors=errors)


def _fuse_candidates(candidates: list[TargetDetection], merge_radius: float) -> list[TargetDetection]:
    fused: list[TargetDetection] = []
    for candidate in sorted(candidates, key=lambda item: item.confidence, reverse=True):
        match_index = _find_match(fused, candidate, merge_radius)
        if match_index is None:
            fused.append(candidate)
            continue
        fused[match_index] = _merge_pair(fused[match_index], candidate)
    return fused


def _find_match(
    existing: list[TargetDetection],
    candidate: TargetDetection,
    merge_radius: float,
) -> int | None:
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
        {
            *(metadata.get("fused_sources", [])),
            first.source,
            second.source,
        }
        - {""}
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
