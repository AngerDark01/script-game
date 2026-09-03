from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from ..models import TargetDetection
from ..profiles import TargetProfile
from ..registry import AlgorithmRegistry


@dataclass(frozen=True)
class DetectorRunResult:
    """Raw detector output grouped by instance, plus isolated failures."""

    candidates: tuple[TargetDetection, ...]
    by_algorithm: Mapping[str, tuple[TargetDetection, ...]] = field(default_factory=dict)
    errors: Mapping[str, str] = field(default_factory=dict)


class DetectorRunner:
    """Execute enabled algorithm instances without applying target policy."""

    def __init__(self, registry: AlgorithmRegistry) -> None:
        self.registry = registry

    def run(self, *, frame: Any, profile: TargetProfile) -> DetectorRunResult:
        by_algorithm: dict[str, tuple[TargetDetection, ...]] = {}
        errors: dict[str, str] = {}
        candidates: list[TargetDetection] = []
        for algorithm_profile in profile.algorithms:
            if not algorithm_profile.enabled:
                continue
            try:
                parameters = dict(algorithm_profile.parameters)
                parameters["target_type"] = profile.target_type
                detector = self.registry.create(algorithm_profile.algorithm_id, parameters)
                detected = tuple(detector.detect(frame) or ())
                if any(not isinstance(item, TargetDetection) for item in detected):
                    raise TypeError("detector output must contain TargetDetection values")
                if any(item.target_type != profile.target_type for item in detected):
                    raise ValueError("detector output target_type must match the target profile")
            except Exception as exc:
                errors[algorithm_profile.instance_id] = f"{type(exc).__name__}: {exc}"
                continue
            by_algorithm[algorithm_profile.instance_id] = detected
            candidates.extend(detected)
        return DetectorRunResult(
            candidates=tuple(candidates),
            by_algorithm=by_algorithm,
            errors=errors,
        )
