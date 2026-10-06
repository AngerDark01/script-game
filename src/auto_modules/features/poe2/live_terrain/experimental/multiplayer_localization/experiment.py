"""One-shot composition for exercising the dual first-frame experiment."""

from __future__ import annotations

from typing import Any, Mapping

from auto_modules.features.poe2.live_terrain.experimental.hybrid_localization.models import (
    HybridFrame,
    PositionAnchor,
)
from auto_modules.features.poe2.live_terrain.terrain_reference import TerrainReference

from .dual_first_frame import DualFirstFrameRegistrar
from .marker_candidates import marker_candidates_from_observation
from .memory_anchors import Poe2DualMemoryAnchorProvider
from .models import DualFirstFrameResult


class DualFirstFrameExperiment:
    """Compose memory anchors, shared observations and dual validation.

    The caller controls capture ordering: call ``read_anchors`` immediately
    before taking the minimap frame, then pass that snapshot to ``register``.
    This keeps the memory read count explicit and makes stale-frame handling a
    caller-visible experiment decision.
    """

    def __init__(
        self,
        anchor_provider: Poe2DualMemoryAnchorProvider,
        registrar: DualFirstFrameRegistrar | None = None,
    ) -> None:
        self.anchor_provider = anchor_provider
        self.registrar = registrar or DualFirstFrameRegistrar()

    def read_anchors(self, expected_instance_id: str) -> Mapping[str, PositionAnchor]:
        return self.anchor_provider.read_once(expected_instance_id)

    def register(
        self,
        frame: HybridFrame,
        *,
        reference: TerrainReference,
        anchors: Mapping[str, PositionAnchor],
        observation: Any,
    ) -> DualFirstFrameResult:
        # First-frame registration is a bounded one-shot operation. Keep one
        # candidate per configured role plus a small ambiguity reserve; the
        # live worker has a separate, larger candidate budget because it does
        # not run the expensive absolute assignment search.
        candidates = marker_candidates_from_observation(observation, max_candidates=4)
        return self.registrar.register(
            frame,
            reference=reference,
            anchors=anchors,
            candidates=candidates,
        )


__all__ = ["DualFirstFrameExperiment"]
