"""Motion-aware two-role marker association facade."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from auto_modules.features.poe2.live_terrain.experimental.multiplayer_localization.marker_association import (
    AssociationResult,
    MarkerAssociator,
)
from auto_modules.features.poe2.live_terrain.experimental.multiplayer_localization.models import PlayerMarkerCandidate


@dataclass(frozen=True, slots=True)
class DualAssociation:
    assignments: Mapping[str, tuple[float, float]]
    ambiguous: bool
    diagnostics: Mapping[str, Any]


class DualRoleAssociator:
    """Use geometry and motion first, with color as a soft identity hint."""

    def __init__(self, *, base_gate: float = 45.0, max_gate: float = 180.0, margin: float = 2.0) -> None:
        self._associator = MarkerAssociator(base_gate=base_gate, max_gate=max_gate, margin=margin)

    def assign(
        self,
        candidates: Sequence[PlayerMarkerCandidate],
        predicted: Mapping[str, tuple[float, float]],
        *,
        identity_hints: Mapping[str, str] | None = None,
        velocities: Mapping[str, tuple[float, float]] | None = None,
        elapsed_ms: Mapping[str, int] | None = None,
        wall_shift: tuple[float, float] = (0.0, 0.0),
    ) -> DualAssociation:
        result: AssociationResult = self._associator.assign(
            candidates,
            predicted,
            identity_hints=identity_hints,
            velocities=velocities,
            elapsed_ms=elapsed_ms,
            wall_shift=wall_shift,
        )
        if identity_hints and len(result.assignment) < len(predicted) and len(candidates) >= len(predicted):
            geometry_result = self._associator.assign(
                candidates,
                predicted,
                identity_hints=None,
                velocities=velocities,
                elapsed_ms=elapsed_ms,
                wall_shift=wall_shift,
            )
            if len(geometry_result.assignment) > len(result.assignment) or (
                len(geometry_result.assignment) == len(result.assignment)
                and not geometry_result.ambiguous
            ):
                result = geometry_result
        return DualAssociation(dict(result.assignment), bool(result.ambiguous), dict(result.diagnostics))
