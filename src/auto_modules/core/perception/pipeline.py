from __future__ import annotations

from typing import Any

from .models import PerceptionRunResult
from .profiles import TargetProfile
from .registry import AlgorithmRegistry
from .stages.fusion import fuse_candidates


class PerceptionPipeline:
    """Compatibility entry point that forwards target runs to PerceptionEngine."""

    def __init__(self, registry: AlgorithmRegistry) -> None:
        from .engine import PerceptionEngine

        self.registry = registry
        self.engine = PerceptionEngine(registry)

    def run(
        self,
        frame: Any,
        profile: TargetProfile,
        *,
        reference: tuple[float, float] | None = None,
    ) -> PerceptionRunResult:
        return self.engine.detect(frame, profile, reference=reference)

    def reset_confirmation(self, profile: TargetProfile | None = None) -> None:
        self.engine.reset_confirmation(profile)


# Compatibility helper retained for callers that imported the old private function.
def _fuse_candidates(candidates, merge_radius):
    return list(fuse_candidates(candidates, merge_radius))
