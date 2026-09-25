"""Bounded local shape correction around an existing registration."""

from __future__ import annotations

from dataclasses import dataclass
import math
from types import MappingProxyType
from typing import Any, Mapping

import numpy as np

from auto_modules.features.poe2.live_terrain.experimental.hybrid_localization.models import (
    AbsoluteRegistration,
    HybridFrame,
    SimilarityTransform2D,
)

from .shape_registration import ShapeScore, score_shape, transform_points


@dataclass(frozen=True)
class SearchBounds:
    width: int
    height: int


@dataclass(frozen=True)
class LocalCorrection:
    accepted: bool
    position: tuple[float, float] | None
    transform: SimilarityTransform2D | None
    covariance: np.ndarray | None
    score: ShapeScore | None
    reason: str
    search_bounds: SearchBounds
    diagnostics: Mapping[str, object]

    def __post_init__(self) -> None:
        if self.covariance is not None:
            covariance = np.array(self.covariance, dtype=np.float64, copy=True)
            covariance.setflags(write=False)
            object.__setattr__(self, "covariance", covariance)
        object.__setattr__(self, "diagnostics", MappingProxyType(dict(self.diagnostics)))


def _offsets(radius: float, step: float) -> tuple[float, ...]:
    if radius <= 0:
        return (0.0,)
    count = int(math.floor(radius / step))
    values = tuple(float(index * step) for index in range(-count, count + 1))
    return values if 0.0 in values else tuple(sorted((*values, 0.0)))


def _reference_boundary(reference: Any) -> np.ndarray:
    boundary = getattr(reference, "wall_layer", reference)
    if hasattr(reference, "walkable_mask"):
        from auto_modules.features.poe2.live_terrain.experimental.hybrid_localization.absolute_registrar import (
            reference_boundary_layer,
        )

        boundary = reference_boundary_layer(reference)
    result = np.asarray(boundary)
    if result.ndim != 2 or result.size == 0:
        raise ValueError("reference boundary must be a non-empty 2-D array")
    return result


class LocalShapeCorrector:
    def __init__(
        self,
        *,
        translation_radius: float = 6.0,
        translation_step: float = 1.0,
        angle_radius: float = 2.0,
        angle_step: float = 1.0,
        scale_radius: float = 0.02,
        scale_step: float = 0.01,
        max_error: float = 2.5,
        min_coverage: float = 0.45,
        min_margin: float = 0.02,
        min_usable_points: int = 8,
    ) -> None:
        values = (translation_radius, translation_step, angle_step, scale_step, max_error)
        if any(float(value) <= 0 for value in values) or angle_radius < 0 or scale_radius < 0:
            raise ValueError("local correction search limits are invalid")
        if not 0 <= min_coverage <= 1 or min_margin < 0 or min_usable_points < 1:
            raise ValueError("local correction acceptance limits are invalid")
        self.translation_radius = float(translation_radius)
        self.translation_step = float(translation_step)
        self.angle_radius = float(angle_radius)
        self.angle_step = float(angle_step)
        self.scale_radius = float(scale_radius)
        self.scale_step = float(scale_step)
        self.max_error = float(max_error)
        self.min_coverage = float(min_coverage)
        self.min_margin = float(min_margin)
        self.min_usable_points = int(min_usable_points)

    def correct(
        self,
        *,
        frame: HybridFrame,
        observed_mask: np.ndarray,
        predicted_position: tuple[float, float],
        registration: AbsoluteRegistration,
        reference: Any,
    ) -> LocalCorrection:
        translations = _offsets(self.translation_radius, self.translation_step)
        bounds = SearchBounds(len(translations), len(translations))
        if int(np.count_nonzero(frame.wall_mask)) < self.min_usable_points:
            return LocalCorrection(
                False,
                None,
                None,
                None,
                None,
                "insufficient_visual_structure",
                bounds,
                {"tested_candidates": 0},
            )
        boundary = _reference_boundary(reference)
        angle_offsets = _offsets(self.angle_radius, self.angle_step)
        scale_offsets = _offsets(self.scale_radius, self.scale_step)
        candidates: list[tuple[float, SimilarityTransform2D, ShapeScore, tuple[float, float]]] = []
        local_player = np.asarray([frame.local_player], dtype=np.float64)
        for angle_delta in angle_offsets:
            for scale_delta in scale_offsets:
                scale = registration.transform.scale + scale_delta
                if scale <= 0:
                    continue
                basis = SimilarityTransform2D(
                    registration.transform.angle_degrees + angle_delta,
                    registration.transform.reflect_horizontal,
                    scale,
                    (0.0, 0.0),
                )
                mapped_player = transform_points(local_player, basis)[0]
                for dx in translations:
                    for dy in translations:
                        position = (predicted_position[0] + dx, predicted_position[1] + dy)
                        transform = SimilarityTransform2D(
                            basis.angle_degrees,
                            basis.reflect_horizontal,
                            basis.scale,
                            (position[0] - mapped_player[0], position[1] - mapped_player[1]),
                        )
                        shape = score_shape(
                            wall_mask=frame.wall_mask,
                            observed_mask=observed_mask,
                            reference_boundary=boundary,
                            transform=transform,
                        )
                        if not math.isfinite(shape.forward_error):
                            continue
                        reverse_error = shape.reverse_error if math.isfinite(shape.reverse_error) else shape.forward_error
                        tangent_error = shape.tangent_error if math.isfinite(shape.tangent_error) else 0.5
                        objective = (
                            shape.forward_error
                            + 0.5 * reverse_error
                            + 0.25 * tangent_error
                            + (1.0 - shape.forward_coverage)
                            + 0.5 * (1.0 - shape.reverse_coverage)
                        )
                        candidates.append((objective, transform, shape, position))
        candidates.sort(key=lambda item: item[0])
        if not candidates:
            return LocalCorrection(False, None, None, None, None, "no_local_candidate", bounds, {"tested_candidates": 0})
        best_error, best_transform, best_shape, best_position = candidates[0]
        second_error = candidates[1][0] if len(candidates) > 1 else float("inf")
        margin = second_error - best_error
        diagnostics = {
            "tested_candidates": len(candidates),
            "objective": best_error,
            "candidate_margin": margin,
            "forward_coverage": best_shape.forward_coverage,
            "reverse_coverage": best_shape.reverse_coverage,
        }
        if best_shape.usable_points < self.min_usable_points:
            return LocalCorrection(False, None, None, None, best_shape, "insufficient_visual_structure", bounds, diagnostics)
        if best_shape.forward_error > self.max_error or best_shape.forward_coverage < self.min_coverage:
            return LocalCorrection(False, None, None, None, best_shape, "shape_quality", bounds, diagnostics)
        if margin < self.min_margin:
            return LocalCorrection(False, None, None, None, best_shape, "candidate_ambiguous", bounds, diagnostics)
        variance = max(
            0.25,
            best_shape.forward_error
            + (1.0 - best_shape.forward_coverage) * 4.0
            + 1.0 / max(margin, 0.1),
        )
        return LocalCorrection(
            True,
            best_position,
            best_transform,
            np.eye(2, dtype=np.float64) * variance,
            best_shape,
            "corrected",
            bounds,
            diagnostics,
        )


__all__ = ["LocalCorrection", "LocalShapeCorrector", "SearchBounds"]
