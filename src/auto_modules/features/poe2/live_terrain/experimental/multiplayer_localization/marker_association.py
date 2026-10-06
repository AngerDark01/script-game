"""Motion-aware association of minimap marker candidates.

This module contains no Qt, process, or game-specific side effects.  It keeps
the association gate proportional to elapsed time and the last observed
screen velocity instead of rejecting a valid marker after a delayed frame.
"""

from __future__ import annotations

import itertools
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from .models import PlayerMarkerCandidate


@dataclass(frozen=True)
class AssociationResult:
    assignment: Mapping[str, tuple[float, float]]
    ambiguous: bool
    diagnostics: Mapping[str, Any]


class MarkerAssociator:
    """Associate candidates with role predictions using adaptive gates."""

    def __init__(self, *, base_gate: float = 45.0, max_gate: float = 180.0, margin: float = 2.0) -> None:
        if base_gate <= 0 or max_gate < base_gate or margin < 0:
            raise ValueError("invalid marker association thresholds")
        self.base_gate = float(base_gate)
        self.max_gate = float(max_gate)
        self.margin = float(margin)

    def assign(
        self,
        candidates: Sequence[PlayerMarkerCandidate],
        predicted: Mapping[str, tuple[float, float]],
        *,
        identity_hints: Mapping[str, str] | None = None,
        velocities: Mapping[str, tuple[float, float]] | None = None,
        elapsed_ms: Mapping[str, int] | None = None,
        wall_shift: tuple[float, float] = (0.0, 0.0),
        pair_geometry: bool = True,
    ) -> AssociationResult:
        visible = tuple(sorted(candidates, key=lambda item: item.confidence, reverse=True)[:6])
        if not visible:
            return AssociationResult({}, False, {"candidate_ids": (), "options": ()})
        hints = identity_hints or {}
        speeds = velocities or {}
        ages = elapsed_ms or {}
        gates: dict[str, float] = {}
        for identity, point in predicted.items():
            velocity = speeds.get(identity, (0.0, 0.0))
            speed = math.hypot(float(velocity[0]), float(velocity[1]))
            age = max(0.0, float(ages.get(identity, 0)) / 1000.0)
            shift = math.hypot(float(wall_shift[0]), float(wall_shift[1]))
            # A delayed frame and a moving role need a larger gate.  The cap
            # prevents an unbounded prediction from accepting arbitrary UI noise.
            gates[identity] = min(
                self.max_gate,
                max(self.base_gate, self.base_gate + speed * age + shift * 1.5),
            )
        # Pair geometry is deliberately a soft term.  It prevents a colour
        # collision from swapping two nearby roles, while still allowing a
        # single role to be associated when its partner is occluded.
        predicted_identities = tuple(predicted)
        predicted_pair_distance = None
        if pair_geometry and len(predicted_identities) == 2:
            predicted_pair_distance = math.dist(
                predicted[predicted_identities[0]], predicted[predicted_identities[1]],
            )
        options: list[tuple[float, tuple[str, ...], tuple[PlayerMarkerCandidate, ...], tuple[float, ...], float | None]] = []
        for count in range(min(len(predicted), len(visible)), 0, -1):
            for selected in itertools.combinations(visible, count):
                for identities in itertools.permutations(predicted, count):
                    if any(
                        identity in hints
                        and hints[identity] != str(candidate.color_features.get("identity_hint") or "")
                        for identity, candidate in zip(identities, selected)
                    ):
                        continue
                    distances = tuple(
                        math.dist(predicted[identity], candidate.local_position)
                        for identity, candidate in zip(identities, selected)
                    )
                    if all(distance <= gates[identity] for identity, distance in zip(identities, distances)):
                        pair_error = None
                        pair_cost = 0.0
                        if predicted_pair_distance is not None and len(selected) == 2:
                            observed_pair_distance = math.dist(
                                selected[0].local_position, selected[1].local_position,
                            )
                            pair_error = abs(observed_pair_distance - predicted_pair_distance)
                            pair_cost = pair_error * 0.75
                        options.append((sum(distances) + pair_cost, identities, selected, distances, pair_error))
            if options:
                break
        # Color is a soft identity hint. If it rejects every candidate while
        # the geometry is still plausible, retry once without the hint so a
        # temporary hue collision cannot erase both tracked roles.
        if not options and hints:
            for count in range(min(len(predicted), len(visible)), 0, -1):
                for selected in itertools.combinations(visible, count):
                    for identities in itertools.permutations(predicted, count):
                        distances = tuple(
                            math.dist(predicted[identity], candidate.local_position)
                            for identity, candidate in zip(identities, selected)
                        )
                        if all(distance <= gates[identity] for identity, distance in zip(identities, distances)):
                            pair_error = None
                            pair_cost = 0.0
                            if predicted_pair_distance is not None and len(selected) == 2:
                                pair_error = abs(
                                    math.dist(selected[0].local_position, selected[1].local_position)
                                    - predicted_pair_distance
                                )
                                pair_cost = pair_error * 0.75
                            options.append((sum(distances) + pair_cost, identities, selected, distances, pair_error))
                if options:
                    break
        options.sort(key=lambda item: item[0])
        diagnostics = {
            "candidate_ids": tuple(item.candidate_id for item in visible),
            "gates": dict(gates),
            "predicted_pair_distance": None if predicted_pair_distance is None else float(predicted_pair_distance),
            "options": tuple(
                {
                    "cost": float(cost),
                    "identities": identities,
                    "candidate_ids": tuple(item.candidate_id for item in selected),
                    "distances": distances,
                    "pair_distance_error": None if pair_error is None else float(pair_error),
                    "pair_geometry_score": None if pair_error is None else float(math.exp(-pair_error / 12.0)),
                }
                for cost, identities, selected, distances, pair_error in options[:4]
            ),
            "identity_hint_fallback": bool(hints and options and any(
                self._hint_mismatch(identity, candidate, hints)
                for _cost, identities, selected, _distances, _pair_error in options[:1]
                for identity, candidate in zip(identities, selected)
            )),
        }
        if options and predicted_pair_distance is not None and len(options[0][2]) == 2:
            diagnostics["observed_pair_distance"] = float(math.dist(
                options[0][2][0].local_position, options[0][2][1].local_position,
            ))
            diagnostics["pair_distance_error"] = float(options[0][4] or 0.0)
            diagnostics["pair_geometry_score"] = float(
                math.exp(-float(options[0][4] or 0.0) / 12.0)
            )
        if not options:
            return AssociationResult({}, False, diagnostics)
        ambiguous = len(options) > 1 and options[1][0] - options[0][0] < self.margin
        if ambiguous:
            return AssociationResult({}, True, diagnostics)
        return AssociationResult(
            {identity: candidate.local_position for identity, candidate in zip(options[0][1], options[0][2])},
            False,
            diagnostics,
        )

    @staticmethod
    def _hint_mismatch(identity: str, candidate: PlayerMarkerCandidate, hints: Mapping[str, str]) -> bool:
        return identity in hints and hints[identity] != str(candidate.color_features.get("identity_hint") or "")


__all__ = ["AssociationResult", "MarkerAssociator"]
