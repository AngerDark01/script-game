"""Strategy B: jointly rank transform hypotheses over multiple keyframes."""

from __future__ import annotations

from dataclasses import dataclass, replace
import math
from typing import Iterable, Sequence

import numpy as np

from auto_modules.core.localization import transform_local_displacement
from auto_modules.features.poe2.live_terrain.experimental.hybrid_localization.models import PositionAnchor, SimilarityTransform2D

from .models import CandidateRegion, MultiFrameEvidence
from .shape_registration import score_shape


@dataclass(frozen=True)
class CandidateHypothesis:
    transform: SimilarityTransform2D
    position: tuple[float, float]
    error: float
    score: float
    support_frames: tuple[int, ...]
    holdout_error: float = float("inf")
    refinement_level: str = "coarse"

    def region(self) -> CandidateRegion:
        return CandidateRegion(self.transform, self.position, None, self.score, self.support_frames)


@dataclass(frozen=True)
class CandidateSet:
    candidates: tuple[CandidateHypothesis, ...]
    evidence_version: int

    @property
    def best(self) -> CandidateHypothesis | None:
        return self.candidates[0] if self.candidates else None


@dataclass(frozen=True)
class SearchLevel:
    name: str
    angle_step: float
    scale_step: float
    translation_step: float


DEFAULT_SEARCH_LEVELS = (
    SearchLevel("medium", 15.0, 0.10, 2.0),
    SearchLevel("refined", 5.0, 0.03, 1.0),
    SearchLevel("fine", 1.0, 0.01, 0.5),
)


def deduplicate_candidates(
    candidates: Iterable[CandidateHypothesis],
    *,
    angle_tol: float = 0.5,
    scale_tol: float = 0.01,
    position_tol: float = 2.0,
) -> tuple[CandidateHypothesis, ...]:
    distinct: list[CandidateHypothesis] = []
    for candidate in sorted(candidates, key=lambda item: item.error):
        duplicate = False
        for old in distinct:
            angle_delta = abs((candidate.transform.angle_degrees - old.transform.angle_degrees + 180) % 360 - 180)
            if (
                candidate.transform.reflect_horizontal == old.transform.reflect_horizontal
                and angle_delta <= angle_tol
                and abs(candidate.transform.scale - old.transform.scale) <= scale_tol
                and math.dist(candidate.position, old.position) <= position_tol
            ):
                duplicate = True
                break
        if not duplicate:
            distinct.append(candidate)
    return tuple(distinct)


def _linear_offset(point: tuple[float, float], transform: SimilarityTransform2D) -> tuple[float, float]:
    return transform_local_displacement(
        point,
        angle_degrees=transform.angle_degrees,
        reflect_horizontal=transform.reflect_horizontal,
        scale=transform.scale,
    )


class JointCandidateStrategy:
    def __init__(
        self,
        *,
        max_candidates: int = 12,
        min_margin: float = 0.05,
        min_support_frames: int = 3,
        max_holdout_error: float = 2.5,
        coarse_angles: tuple[float, ...] = tuple(float(value) for value in range(0, 360, 45)),
        coarse_scales: tuple[float, ...] = (0.55, 0.75, 1.0, 1.25, 1.5),
        search_levels: tuple[SearchLevel, ...] = DEFAULT_SEARCH_LEVELS,
        max_refine_basins: int = 4,
    ) -> None:
        if max_candidates < 1 or min_margin < 0 or min_support_frames < 2 or max_holdout_error <= 0:
            raise ValueError("invalid candidate strategy limits")
        if not coarse_angles or not coarse_scales or any(float(value) <= 0 for value in coarse_scales):
            raise ValueError("coarse search variants must not be empty")
        self.max_candidates = int(max_candidates)
        self.min_margin = float(min_margin)
        self.min_support_frames = int(min_support_frames)
        self.max_holdout_error = float(max_holdout_error)
        self.coarse_angles = tuple(float(value) for value in coarse_angles)
        self.coarse_scales = tuple(float(value) for value in coarse_scales)
        self.search_levels = tuple(search_levels)
        self.max_refine_basins = max(1, int(max_refine_basins))
        self._candidates: tuple[CandidateHypothesis, ...] = ()
        self._version = -1
        self._reference_origin = (0.0, 0.0)

    @property
    def minimum_evidence_frames(self) -> int:
        """Return the number of keyframes required for joint scoring."""
        return int(self.min_support_frames)

    def reset(self) -> None:
        """Discard candidates learned from a previous session or map instance."""
        self._candidates = ()
        self._version = -1
        self._reference_origin = (0.0, 0.0)

    def seed(self, candidates: Iterable[CandidateHypothesis], *, evidence_version: int) -> CandidateSet:
        self._candidates = deduplicate_candidates(candidates)[: self.max_candidates]
        self._version = int(evidence_version)
        return CandidateSet(self._absolute_candidates(self._candidates), self._version)

    def update(
        self,
        frames: Sequence[MultiFrameEvidence],
        *,
        anchor: PositionAnchor,
        reference_boundary: np.ndarray,
        evidence_version: int | None = None,
        reference_origin: tuple[float, float] = (0.0, 0.0),
    ) -> CandidateSet:
        if not frames:
            return CandidateSet(self._absolute_candidates(self._candidates), self._version)
        origin = (float(reference_origin[0]), float(reference_origin[1]))
        if origin != self._reference_origin:
            self._candidates = ()
            self._reference_origin = origin
        local_anchor = replace(
            anchor,
            position=(anchor.position[0] - origin[0], anchor.position[1] - origin[1]),
        )
        hypotheses = self._candidates or self._seed_from_anchor(frames[0], local_anchor)
        evaluated = self._evaluate_hypotheses(hypotheses, frames, reference_boundary)
        for level in self.search_levels:
            expanded = self._expand_hypotheses(
                evaluated[: self.max_refine_basins],
                frame=frames[0],
                anchor=anchor,
                level=level,
            )
            evaluated = self._evaluate_hypotheses(expanded, frames, reference_boundary)
        self._candidates = deduplicate_candidates(evaluated)[: self.max_candidates]
        observed_version = max(item.frame.frame_id for item in frames) if evidence_version is None else int(evidence_version)
        self._version = max(self._version, observed_version)
        return CandidateSet(self._absolute_candidates(self._candidates), self._version)

    def _absolute_candidates(
        self,
        candidates: Sequence[CandidateHypothesis],
    ) -> tuple[CandidateHypothesis, ...]:
        ox, oy = self._reference_origin
        if ox == 0.0 and oy == 0.0:
            return tuple(candidates)
        return tuple(
            replace(
                candidate,
                position=(candidate.position[0] + ox, candidate.position[1] + oy),
                transform=replace(
                    candidate.transform,
                    translation=(
                        candidate.transform.translation[0] + ox,
                        candidate.transform.translation[1] + oy,
                    ),
                ),
            )
            for candidate in candidates
        )

    def _evaluate_hypotheses(
        self,
        hypotheses: Sequence[CandidateHypothesis],
        frames: Sequence[MultiFrameEvidence],
        reference_boundary: np.ndarray,
    ) -> tuple[CandidateHypothesis, ...]:
        training = tuple(frames[:-1]) if len(frames) >= self.min_support_frames else tuple(frames)
        holdout = frames[-1] if len(frames) >= self.min_support_frames else None
        updated: list[CandidateHypothesis] = []
        for candidate in hypotheses:
            total_error = 0.0
            support: list[int] = []
            for item in training:
                score = self._score_item(item, candidate.transform, reference_boundary)
                if np.isfinite(score.forward_error):
                    reverse_error = score.reverse_error if np.isfinite(score.reverse_error) else score.forward_error
                    tangent_error = score.tangent_error if np.isfinite(score.tangent_error) else 0.5
                    total_error += (
                        score.forward_error
                        + 0.5 * reverse_error
                        + 0.25 * tangent_error
                        + (1.0 - score.forward_coverage)
                        + 0.5 * (1.0 - score.reverse_coverage)
                    )
                else:
                    total_error += 100.0
                if score.usable_points:
                    support.append(item.frame.frame_id)
            holdout_error = float("inf")
            if holdout is not None:
                validation = self._score_item(holdout, candidate.transform, reference_boundary)
                holdout_error = validation.forward_error
                if validation.usable_points:
                    support.append(holdout.frame.frame_id)
            current = frames[-1]
            current_position = self._position_for(current, candidate.transform)
            updated.append(replace(
                candidate,
                position=current_position,
                error=total_error,
                score=1.0 / (1.0 + total_error),
                support_frames=tuple(support),
                holdout_error=holdout_error,
            ))
        return deduplicate_candidates(updated)[: self.max_candidates]

    def _expand_hypotheses(
        self,
        candidates: Sequence[CandidateHypothesis],
        *,
        frame: MultiFrameEvidence,
        anchor: PositionAnchor,
        level: SearchLevel,
    ) -> tuple[CandidateHypothesis, ...]:
        local_player = (
            frame.frame.local_player[0] + frame.local_offset[0],
            frame.frame.local_player[1] + frame.local_offset[1],
        )
        expanded: list[CandidateHypothesis] = []
        for candidate in candidates:
            for angle_delta in (-level.angle_step, 0.0, level.angle_step):
                for scale_delta in (-level.scale_step, 0.0, level.scale_step):
                    scale = candidate.transform.scale + scale_delta
                    if scale <= 0:
                        continue
                    basis = SimilarityTransform2D(
                        candidate.transform.angle_degrees + angle_delta,
                        candidate.transform.reflect_horizontal,
                        scale,
                        (0.0, 0.0),
                    )
                    mapped_player = _linear_offset(local_player, basis)
                    for dx in (-level.translation_step, 0.0, level.translation_step):
                        for dy in (-level.translation_step, 0.0, level.translation_step):
                            transform = replace(
                                basis,
                                translation=(
                                    anchor.position[0] - mapped_player[0] + dx,
                                    anchor.position[1] - mapped_player[1] + dy,
                                ),
                            )
                            expanded.append(
                                CandidateHypothesis(
                                    transform,
                                    (anchor.position[0] + dx, anchor.position[1] + dy),
                                    float("inf"),
                                    0.0,
                                    (),
                                    refinement_level=level.name,
                                )
                            )
        return deduplicate_candidates(expanded, angle_tol=0.1, scale_tol=0.001, position_tol=0.1)

    def confirmable(self, result: CandidateSet) -> bool:
        if not result.candidates:
            return False
        best = result.candidates[0]
        if len(best.support_frames) < self.min_support_frames:
            return False
        if not math.isfinite(best.holdout_error) or best.holdout_error > self.max_holdout_error:
            return False
        if len(result.candidates) == 1:
            return True
        return (result.candidates[1].error - best.error) >= self.min_margin

    def _seed_from_anchor(self, frame: MultiFrameEvidence, anchor: PositionAnchor) -> tuple[CandidateHypothesis, ...]:
        local_player = (
            frame.frame.local_player[0] + frame.local_offset[0],
            frame.frame.local_player[1] + frame.local_offset[1],
        )
        hypotheses = []
        for angle in self.coarse_angles:
            for reflect in (False, True):
                for scale in self.coarse_scales:
                    basis = SimilarityTransform2D(angle, reflect, scale, (0.0, 0.0))
                    mapped_player = _linear_offset(local_player, basis)
                    transform = replace(
                        basis,
                        translation=(anchor.position[0] - mapped_player[0], anchor.position[1] - mapped_player[1]),
                    )
                    hypotheses.append(CandidateHypothesis(transform, anchor.position, 0.0, 0.0, (), refinement_level="coarse"))
        return tuple(hypotheses)

    @staticmethod
    def _score_item(item: MultiFrameEvidence, transform: SimilarityTransform2D, reference_boundary: np.ndarray):
        offset = _linear_offset(item.local_offset, transform)
        shifted = replace(
            transform,
            translation=(transform.translation[0] + offset[0], transform.translation[1] + offset[1]),
        )
        return score_shape(
            wall_mask=item.frame.wall_mask,
            observed_mask=item.observed_mask,
            reference_boundary=reference_boundary,
            transform=shifted,
            # Tangent agreement is valuable for the final validator, but its
            # nearest-neighbour scan dominates the bounded coarse search.
            include_tangent=False,
            # Reverse rasterization is reserved for the final acceptance
            # gates; the joint coarse search only needs forward wall overlap.
            include_reverse=False,
        )

    @staticmethod
    def _position_for(item: MultiFrameEvidence, transform: SimilarityTransform2D) -> tuple[float, float]:
        point = (
            item.frame.local_player[0] + item.local_offset[0],
            item.frame.local_player[1] + item.local_offset[1],
        )
        mapped = _linear_offset(point, transform)
        return mapped[0] + transform.translation[0], mapped[1] + transform.translation[1]


__all__ = [
    "CandidateHypothesis",
    "CandidateSet",
    "DEFAULT_SEARCH_LEVELS",
    "JointCandidateStrategy",
    "SearchLevel",
    "deduplicate_candidates",
]
