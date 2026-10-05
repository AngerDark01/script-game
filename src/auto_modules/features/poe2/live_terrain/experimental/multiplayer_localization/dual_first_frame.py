"""Two-player first-frame registration for the PoE2 experiment.

The existing single-player registrar remains the authority for finding one
orientation/scale/translation basin.  This module tries both marker-to-memory
assignments, then requires the same transform to explain both native anchors.
It deliberately has no frame-to-frame tracking or input/device behavior.
"""

from __future__ import annotations

import itertools
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from typing import Any

import cv2
import numpy as np

from auto_modules.core.localization import LocalizationResult
from auto_modules.features.poe2.live_terrain.experimental.hybrid_localization.absolute_registrar import (
    AnchoredAbsoluteRegistrar,
    AnchoredRegistrationConfig,
    crop_terrain_around_anchor,
    reference_boundary_layer,
)
from auto_modules.features.poe2.live_terrain.experimental.hybrid_localization.models import (
    AbsoluteRegistration,
    HybridFrame,
    PositionAnchor,
    SimilarityTransform2D,
)
from auto_modules.features.poe2.live_terrain.experimental.hybrid_localization.similarity_search import (
    terrain_edges,
    transform_feature,
    transform_local_point,
)
from auto_modules.features.poe2.live_terrain.terrain_reference import TerrainReference

from .models import DualFirstFrameResult, PlayerLocalization, PlayerMarkerCandidate


@dataclass(frozen=True)
class DualFirstFrameConfig:
    """Acceptance policy for the two-player wrapper."""

    max_anchor_error: float = 12.0
    min_marker_confidence: float = 0.25
    minimum_pair_confidence: float = 0.70
    assignment_margin: float = 0.03
    pair_distance_tolerance: float = 8.0
    # A midpoint registration has no direct two-point translation fit.  Keep
    # the independent residual gate tighter than the ordinary pair gate so a
    # wrong orientation cannot hide behind the midpoint anchor.
    midpoint_max_anchor_error: float = 6.0
    # A two-point similarity transform becomes ill-conditioned when the
    # marker baseline is comparable to one marker's pixel uncertainty.  In
    # that case use the midpoint as the absolute anchor and let wall geometry
    # determine orientation and scale instead of trusting the noisy angle.
    minimum_screen_baseline: float = 16.0
    minimum_native_baseline: float = 12.0
    joint_angle_radius: float = 12.0
    joint_scale_radius: float = 0.12

    def __post_init__(self) -> None:
        if not math.isfinite(float(self.max_anchor_error)) or self.max_anchor_error <= 0:
            raise ValueError("max_anchor_error must be positive and finite")
        if not 0.0 <= float(self.min_marker_confidence) <= 1.0:
            raise ValueError("min_marker_confidence must be between zero and one")
        if not 0.0 <= float(self.minimum_pair_confidence) <= 1.0:
            raise ValueError("minimum_pair_confidence must be between zero and one")
        if float(self.assignment_margin) < 0.0 or not math.isfinite(float(self.assignment_margin)):
            raise ValueError("assignment_margin must be finite and non-negative")
        for name in (
            "pair_distance_tolerance",
            "midpoint_max_anchor_error",
            "minimum_screen_baseline",
            "minimum_native_baseline",
            "joint_angle_radius",
            "joint_scale_radius",
        ):
            value = float(getattr(self, name))
            if not math.isfinite(value) or value <= 0.0:
                raise ValueError(f"{name} must be positive and finite")


@dataclass(frozen=True)
class _AssignmentEvaluation:
    assignment: Mapping[str, PlayerMarkerCandidate]
    registration: AbsoluteRegistration
    players: Mapping[str, PlayerLocalization]
    score: float
    mean_anchor_error: float
    joint: Mapping[str, Any]


def _joint_similarity_estimates(
    screen_first: tuple[float, float],
    screen_second: tuple[float, float],
    native_first: tuple[float, float],
    native_second: tuple[float, float],
) -> tuple[dict[str, Any], ...]:
    """Estimate the only similarity transform that explains both anchors."""
    screen_delta = (
        float(screen_second[0]) - float(screen_first[0]),
        float(screen_second[1]) - float(screen_first[1]),
    )
    native_delta = (
        float(native_second[0]) - float(native_first[0]),
        float(native_second[1]) - float(native_first[1]),
    )
    screen_length = math.hypot(*screen_delta)
    native_length = math.hypot(*native_delta)
    if screen_length <= 1e-6 or native_length <= 1e-6:
        return ()
    native_angle = math.atan2(native_delta[1], native_delta[0])
    estimates: list[dict[str, Any]] = []
    for reflected in (False, True):
        vector = (-screen_delta[0], screen_delta[1]) if reflected else screen_delta
        source_angle = math.atan2(vector[1], vector[0])
        angle = math.degrees(source_angle - native_angle)
        scale = native_length / screen_length
        radians = math.radians(angle)
        mapped = (
            scale * (math.cos(radians) * vector[0] + math.sin(radians) * vector[1]),
            scale * (-math.sin(radians) * vector[0] + math.cos(radians) * vector[1]),
        )
        vector_error = math.dist(mapped, native_delta)
        screen_mid = (
            (float(screen_first[0]) + float(screen_second[0])) / 2.0,
            (float(screen_first[1]) + float(screen_second[1])) / 2.0,
        )
        native_mid = (
            (float(native_first[0]) + float(native_second[0])) / 2.0,
            (float(native_first[1]) + float(native_second[1])) / 2.0,
        )
        estimates.append(
            {
                "angle": float(angle % 360.0),
                "reflect_horizontal": reflected,
                "scale": float(scale),
                "screen_midpoint": screen_mid,
                "native_midpoint": native_mid,
                "screen_delta": screen_delta,
                "native_delta": native_delta,
                "pair_distance_error": float(vector_error),
            }
        )
    return tuple(estimates)


def _joint_similarity_estimate(*args: Any, **kwargs: Any) -> dict[str, Any] | None:
    estimates = _joint_similarity_estimates(*args, **kwargs)
    return estimates[0] if estimates else None


def _reference_match_terrain(reference: TerrainReference) -> np.ndarray:
    """Build the same thin wall-boundary layer used by the generic matcher.

    ``TerrainReference.wall_layer`` is a storage layer: every non-walkable
    cell is 255, including the entire blocked/unknown interior.  Passing that
    layer directly through ``terrain_edges`` turns the whole blocked region
    into matching evidence.  That makes the two direct mirror solutions look
    nearly identical and lets the pair baseline decide the direction.  The
    matcher must compare against the walkable boundary only.
    """
    walkable = np.asarray(reference.walkable_mask, dtype=bool)
    boundary = reference_boundary_layer(reference) > 0
    terrain = np.zeros(reference.shape, dtype=np.uint8)
    terrain[walkable] = 60
    terrain[boundary] = 235
    return terrain


def _validate_inputs(
    frame: HybridFrame,
    anchors: Mapping[str, PositionAnchor],
    candidates: Sequence[PlayerMarkerCandidate],
) -> tuple[tuple[str, ...], tuple[PlayerMarkerCandidate, ...], str | None]:
    identities = tuple(str(identity) for identity in anchors)
    marker_candidates = tuple(candidates)
    if len(identities) != 2:
        return identities, marker_candidates, "exactly two memory anchors are required for this experiment"
    if len(marker_candidates) < 2:
        return identities, marker_candidates, "exactly two minimap marker candidates are required (at least two are needed)"
    if len({candidate.candidate_id for candidate in marker_candidates}) != len(marker_candidates):
        return identities, marker_candidates, "marker candidate ids must be unique"
    if frame.wall_mask.ndim != 2 or frame.wall_mask.size == 0:
        return identities, marker_candidates, "frame wall mask must be a non-empty 2-D image"
    height, width = frame.wall_mask.shape
    if any(
        not (0.0 <= candidate.local_position[0] < width)
        or not (0.0 <= candidate.local_position[1] < height)
        for candidate in marker_candidates
    ):
        return identities, marker_candidates, "marker candidate is outside the captured minimap"
    area_instances = {anchor.area_instance for anchor in anchors.values()}
    if len(area_instances) != 1:
        return identities, marker_candidates, "memory anchors must belong to one area instance"
    if any(candidate.confidence < 0.0 for candidate in marker_candidates):
        return identities, marker_candidates, "marker candidate confidence is invalid"
    return identities, marker_candidates, None


class DualFirstFrameRegistrar:
    """Validate two player markers against one single-frame registration.

    The memory anchors are trusted only as absolute positions.  Marker colors
    are not used to infer identity: both possible assignments are evaluated,
    and identity is selected only when one assignment is spatially consistent.
    """

    def __init__(
        self,
        registrar: AnchoredAbsoluteRegistrar | None = None,
        *,
        config: DualFirstFrameConfig | None = None,
    ) -> None:
        if registrar is None:
            # The dual path has no trusted center.  Do not inherit the
            # single-player center/top-band clearing policy: both characters
            # may be off-center and every visible wall is matching evidence.
            registrar = AnchoredAbsoluteRegistrar(
                AnchoredRegistrationConfig(
                    top_exclusion_rows=0,
                    player_clear_radius=0,
                )
            )
        self.registrar = registrar
        self.config = config or DualFirstFrameConfig()
        self.last_diagnostics: Mapping[str, Any] = {}

    def register(
        self,
        frame: HybridFrame,
        *,
        reference: TerrainReference,
        anchors: Mapping[str, PositionAnchor],
        candidates: Sequence[PlayerMarkerCandidate],
    ) -> DualFirstFrameResult:
        if not isinstance(frame, HybridFrame):
            raise TypeError("frame must be a HybridFrame")
        identities, marker_candidates, input_error = _validate_inputs(frame, anchors, candidates)
        if input_error is not None:
            return self._result(
                status="insufficient",
                reason=input_error,
                diagnostics={
                    "identity_count": len(identities),
                    "candidate_count": len(marker_candidates),
                },
            )
        low_confidence = [
            candidate.candidate_id
            for candidate in marker_candidates
            if candidate.confidence < self.config.min_marker_confidence
        ]
        marker_candidates = tuple(
            candidate for candidate in marker_candidates
            if candidate.confidence >= self.config.min_marker_confidence
        )
        if len(marker_candidates) < 2:
            return self._result(
                status="insufficient",
                reason="fewer than two marker candidates pass the confidence gate",
                diagnostics={
                    "low_confidence_candidates": low_confidence,
                    "candidate_count": len(marker_candidates),
                },
            )

        evaluations: list[_AssignmentEvaluation] = []
        failures: list[dict[str, Any]] = []
        pair_mismatch_count = 0
        # When the detector returns extra compact colored components, evaluate
        # every ordered pair instead of letting the first two noisy contours
        # decide the whole registration. For the normal two-player case this
        # remains exactly two assignments.
        for permutation in itertools.permutations(marker_candidates, len(identities)):
            assignment = dict(zip(identities, permutation))
            primary_identity = identities[0]
            primary_candidate = assignment[primary_identity]
            primary_frame = replace(frame, local_player=primary_candidate.local_position)
            joint_estimates = _joint_similarity_estimates(
                primary_candidate.local_position,
                assignment[identities[1]].local_position,
                anchors[primary_identity].position,
                anchors[identities[1]].position,
            )
            if not joint_estimates:
                failures.append(
                    {
                        "assignment": {identity: assignment[identity].candidate_id for identity in identities},
                        "reason": "marker or memory anchor pair is degenerate",
                    }
                )
                continue
            joint_estimates = tuple(
                {
                    **joint,
                    "screen_baseline": float(
                        math.hypot(*joint["screen_delta"])
                    ),
                    "native_baseline": float(
                        math.hypot(*joint["native_delta"])
                    ),
                    "pair_mode": self._pair_mode(joint),
                }
                for joint in joint_estimates
            )
            if not isinstance(self.registrar, AnchoredAbsoluteRegistrar):
                joint_estimates = joint_estimates[:1]
            elif any(item["pair_mode"] == "midpoint_geometry" for item in joint_estimates):
                # The midpoint search below evaluates both reflection variants
                # itself.  Running the two unstable pair seeds again would
                # duplicate the same expensive geometry scan.
                joint_estimates = joint_estimates[:1]
            for joint in joint_estimates:
                if joint["pair_mode"] == "midpoint_geometry":
                    registration = self._register_near_midpoint_geometry(
                        frame,
                        primary_frame=primary_frame,
                        reference=reference,
                        first_anchor=anchors[primary_identity],
                        second_anchor=anchors[identities[1]],
                        joint=joint,
                    )
                else:
                    registration = self._register_near_joint_estimate(
                        primary_frame,
                        reference=reference,
                        anchor=anchors[primary_identity],
                        joint=joint,
                    )
                if registration is None:
                    failures.append(
                        {
                            "assignment": {identity: assignment[identity].candidate_id for identity in identities},
                            "joint": dict(joint),
                            "reason": dict(self.registrar.last_diagnostics),
                        }
                    )
                    continue
                self._evaluate_assignment(
                    evaluations,
                    failures,
                    assignment=assignment,
                    identities=identities,
                    frame=frame,
                    anchors=anchors,
                    registration=registration,
                    joint=joint,
                )
            continue

        pair_mismatch_count = sum(
            1 for failure in failures
            if failure.get("reason") == "same transform does not explain both memory anchors"
        )
        evaluations.sort(key=lambda item: (item.score, -item.mean_anchor_error), reverse=True)
        diagnostics: dict[str, Any] = {
            "identity_count": len(identities),
            "candidate_count": len(marker_candidates),
            "assignment_count": math.factorial(len(marker_candidates))
            // math.factorial(len(marker_candidates) - len(identities)),
            "evaluated_assignment_count": len(evaluations),
            "failed_assignments": failures,
            "max_anchor_error": self.config.max_anchor_error,
            "midpoint_max_anchor_error": self.config.midpoint_max_anchor_error,
            "minimum_pair_confidence": self.config.minimum_pair_confidence,
            "evaluated_variant_count": len(evaluations),
        }
        if not evaluations:
            return self._result(
                status="rejected",
                reason=(
                    "same transform does not explain both memory anchors"
                    if pair_mismatch_count
                    else "no marker-to-memory assignment produced a registration"
                ),
                diagnostics=diagnostics,
            )
        best = evaluations[0]
        diagnostics.update(
            {
                "best_pair_confidence": best.score,
                "best_mean_anchor_error": best.mean_anchor_error,
                "best_anchor_quality": float(best.joint.get("anchor_quality", 0.0)),
                "best_pair_geometry_confidence": float(best.joint.get("pair_confidence", 0.0)),
                "best_shape_quality": float(best.joint.get("shape_quality", 0.0)),
                "best_profile_consistency": float(best.joint.get("profile_consistency", 0.0)),
                "best_assignment": {
                    identity: best.assignment[identity].candidate_id
                    for identity in identities
                },
                "registration": dict(best.registration.diagnostics),
                "joint_initialization": dict(best.joint),
            }
        )
        if best.score < self.config.minimum_pair_confidence:
            return self._result(
                status="rejected",
                reason="both-player pair confidence is below threshold",
                primary_registration=best.registration,
                players=best.players,
                diagnostics=diagnostics,
            )
        by_assignment: dict[tuple[str, ...], _AssignmentEvaluation] = {}
        for evaluation in evaluations:
            key = tuple(evaluation.assignment[identity].candidate_id for identity in identities)
            previous = by_assignment.get(key)
            if previous is None or evaluation.score > previous.score:
                by_assignment[key] = evaluation
        assignment_results = sorted(
            by_assignment.values(),
            key=lambda item: (item.score, -item.mean_anchor_error),
            reverse=True,
        )
        if len(assignment_results) > 1:
            margin = assignment_results[0].score - assignment_results[1].score
            diagnostics["assignment_margin"] = margin
            diagnostics["assignment_scores"] = {
                ",".join(item.assignment[identity].candidate_id for identity in identities): item.score
                for item in assignment_results
            }
            if margin < self.config.assignment_margin:
                return self._result(
                    status="ambiguous",
                    reason="two marker-to-memory assignments are too close",
                    primary_registration=best.registration,
                    players=best.players,
                    diagnostics=diagnostics,
                )
        return self._result(
            status="accepted",
            reason="one transform explains both player markers and memory anchors",
            primary_registration=best.registration,
            players=best.players,
            diagnostics=diagnostics,
        )

    def _pair_mode(self, joint: Mapping[str, Any]) -> str:
        """Choose a numerically stable registration path for one marker pair."""
        if (
            float(math.hypot(*joint["screen_delta"])) < self.config.minimum_screen_baseline
            or float(math.hypot(*joint["native_delta"])) < self.config.minimum_native_baseline
        ):
            return "midpoint_geometry"
        return "direct_pair"

    def _register_near_midpoint_geometry(
        self,
        frame: HybridFrame,
        *,
        primary_frame: HybridFrame,
        reference: TerrainReference,
        first_anchor: PositionAnchor,
        second_anchor: PositionAnchor,
        joint: Mapping[str, Any],
    ) -> AbsoluteRegistration | None:
        """Register a close pair around its midpoint instead of its angle.

        The midpoint remains an absolute memory anchor, while the original
        two markers are retained for the post-registration identity/error
        check.  This removes the unstable division by a tiny pair baseline
        from the orientation/scale estimate.
        """
        screen_midpoint = (
            float(joint["screen_midpoint"][0]),
            float(joint["screen_midpoint"][1]),
        )
        native_midpoint = (
            float(joint["native_midpoint"][0]),
            float(joint["native_midpoint"][1]),
        )
        midpoint_frame = replace(frame, local_player=screen_midpoint)
        midpoint_anchor = PositionAnchor(
            position=native_midpoint,
            area_instance=first_anchor.area_instance,
            captured_at_ms=max(first_anchor.captured_at_ms, second_anchor.captured_at_ms),
            source="poe2_dual_midpoint",
            confidence=min(first_anchor.confidence, second_anchor.confidence),
        )
        if isinstance(self.registrar, AnchoredAbsoluteRegistrar):
            base = self.registrar.config
            # A short baseline is not a usable orientation estimator.  The
            # direct two-point transform can always force both markers onto
            # the memory anchors, so its anchor error and pair confidence do
            # not independently validate the direction.  Use the midpoint
            # only as the absolute translation anchor; let wall geometry pick
            # the orientation and scale basin.
            return self._midpoint_shape_registration(
                midpoint_frame,
                reference=reference,
                midpoint_anchor=midpoint_anchor,
                first_anchor=first_anchor,
                second_anchor=second_anchor,
                first_marker=primary_frame.local_player,
                second_marker=(
                    float(joint["screen_midpoint"][0])
                    + float(joint["screen_delta"][0]) / 2.0,
                    float(joint["screen_midpoint"][1])
                    + float(joint["screen_delta"][1]) / 2.0,
                ),
                estimated_scale=float(joint["scale"]),
                config=base,
            )
        else:
            registration = self.registrar.register(
                midpoint_frame,
                reference=reference,
                anchor=midpoint_anchor,
            )
            if registration is not None:
                return registration
        # Keep the caller's primary frame available to custom registrars that
        # explicitly support a midpoint fallback but decline the first pass.
        return self.registrar.register(
            primary_frame,
            reference=reference,
            anchor=first_anchor,
        )

    def _midpoint_shape_registration(
        self,
        frame: HybridFrame,
        *,
        reference: TerrainReference,
        midpoint_anchor: PositionAnchor,
        first_anchor: PositionAnchor,
        second_anchor: PositionAnchor,
        first_marker: tuple[float, float],
        second_marker: tuple[float, float],
        estimated_scale: float,
        config: AnchoredRegistrationConfig,
    ) -> AbsoluteRegistration | None:
        """Find a close-pair transform from wall geometry plus anchor residuals.

        The midpoint fixes translation, while angle/reflection/scale are
        searched independently.  The two known native anchors are a soft
        geometric check, not the source of the orientation.  This avoids the
        unstable angle from a short two-point baseline while retaining enough
        scale information to keep the search bounded.
        """
        terrain = _reference_match_terrain(reference)
        capture_size = max(frame.wall_mask.shape)
        crop_factor = capture_size / float(config.capture_reference_size)
        crop_radius = max(1, round(config.refine_crop_radius * crop_factor))
        local_terrain, crop_bounds = crop_terrain_around_anchor(
            terrain,
            midpoint_anchor.position,
            crop_radius,
        )
        edge = terrain_edges(local_terrain)
        distance = cv2.distanceTransform(
            np.where(edge > 0, 0, 255).astype(np.uint8),
            cv2.DIST_L2,
            3,
        )
        scale_radius = min(
            0.14,
            max(
                float(self.config.joint_scale_radius),
                float(config.refine_scale_radius),
            ),
        )
        scale_step = max(
            0.04,
            min(float(config.refine_scale_step), scale_radius / 6.0),
        )
        scale_values = tuple(
            sorted(
                {
                    round(max(0.20, estimated_scale + offset), 3)
                    for offset in np.arange(
                        -scale_radius,
                        scale_radius + scale_step * 0.5,
                        scale_step,
                    )
                }
            )
        )
        local_anchor = (
            float(midpoint_anchor.position[0] - crop_bounds[0]),
            float(midpoint_anchor.position[1] - crop_bounds[1]),
        )

        def evaluate(angle: float, reflected: bool, scale: float) -> dict[str, Any] | None:
            transformed = transform_feature(
                frame.wall_mask,
                frame.local_player,
                angle=angle,
                reflect_horizontal=reflected,
                scale=scale,
            )
            local_translation = (
                local_anchor[0] - transformed.player_position[0],
                local_anchor[1] - transformed.player_position[1],
            )
            translation = (
                local_translation[0] + float(crop_bounds[0]),
                local_translation[1] + float(crop_bounds[1]),
            )
            mask = transformed.mask > 0
            x, y = round(local_translation[0]), round(local_translation[1])
            x0, y0 = max(0, x), max(0, y)
            x1, y1 = min(edge.shape[1], x + mask.shape[1]), min(edge.shape[0], y + mask.shape[0])
            if x0 >= x1 or y0 >= y1:
                return None
            local_mask = mask[y0 - y : y1 - y, x0 - x : x1 - x]
            pixels = int(np.count_nonzero(local_mask))
            if pixels < 8:
                return None
            coverage = float(np.mean(distance[y0:y1, x0:x1][local_mask] <= 4.0))
            mapped_first = transform_local_point(
                frame.wall_mask.shape,
                first_marker,
                angle=angle,
                reflect_horizontal=reflected,
                scale=scale,
                translation=translation,
            )
            mapped_second = transform_local_point(
                frame.wall_mask.shape,
                second_marker,
                angle=angle,
                reflect_horizontal=reflected,
                scale=scale,
                translation=translation,
            )
            first_error = math.dist(mapped_first, first_anchor.position)
            second_error = math.dist(mapped_second, second_anchor.position)
            mean_error = (first_error + second_error) / 2.0
            pair_score = math.exp(-mean_error / max(self.config.pair_distance_tolerance, 1e-6))
            score = coverage * 0.55 + pair_score * 0.45
            return {
                "angle": float(angle % 360.0),
                "reflect_horizontal": bool(reflected),
                "scale": float(scale),
                "translation": translation,
                "coverage": coverage,
                "pair_score": pair_score,
                "score": score,
                "first_error": first_error,
                "second_error": second_error,
                "mean_error": mean_error,
            }

        coarse: list[dict[str, Any]] = []
        for angle in config.coarse_angles:
            for reflected in config.coarse_reflections:
                for scale in scale_values:
                    candidate = evaluate(float(angle), bool(reflected), float(scale))
                    if candidate is not None:
                        coarse.append(candidate)
        if not coarse:
            self.registrar.last_diagnostics = {
                "status": "rejected",
                "reason": "midpoint shape search produced no candidates",
                "midpoint_search_candidates": 0,
            }
            return None
        coarse.sort(key=lambda item: item["score"], reverse=True)
        seeds = coarse[: max(2, min(int(config.refine_seed_count), 2))]
        refined: list[dict[str, Any]] = list(seeds)
        angle_radius = max(
            float(config.refine_angle_radius),
            float(self.config.joint_angle_radius),
            16.0,
        )
        angle_step = max(3.0, float(config.refine_angle_step))
        for seed in seeds:
            for angle in np.arange(
                float(seed["angle"]) - angle_radius,
                float(seed["angle"]) + angle_radius + angle_step * 0.5,
                angle_step,
            ):
                for scale in np.arange(
                    max(0.20, float(seed["scale"]) - scale_radius),
                    float(seed["scale"]) + scale_radius + scale_step * 0.5,
                    scale_step,
                ):
                    candidate = evaluate(float(angle), bool(seed["reflect_horizontal"]), float(scale))
                    if candidate is not None:
                        refined.append(candidate)
        best = max(refined, key=lambda item: item["score"])
        if (
            best["coverage"] < config.minimum_forward_coverage_when_anchored
            or best["mean_error"] > self.config.midpoint_max_anchor_error
        ):
            self.registrar.last_diagnostics = {
                "status": "rejected",
                "reason": "midpoint shape candidate failed independent geometry gates",
                "best_forward_coverage": float(best["coverage"]),
                "midpoint_mean_anchor_error": float(best["mean_error"]),
                "midpoint_max_anchor_error": self.config.midpoint_max_anchor_error,
                "minimum_forward_coverage_when_anchored": (
                    config.minimum_forward_coverage_when_anchored
                ),
                "midpoint_search_candidates": len(coarse) + len(refined),
                "best_angle": float(best["angle"]),
                "best_reflection": bool(best["reflect_horizontal"]),
                "best_scale": float(best["scale"]),
                "reference_boundary_pixels": int(np.count_nonzero(edge)),
            }
            return None
        return AbsoluteRegistration(
            result=LocalizationResult(
                position=midpoint_anchor.position,
                confidence=float(best["score"]),
                source="dual_midpoint_geometry",
                registration_valid=True,
                metadata={
                    "joint_shape_coverage": float(best["coverage"]),
                    "midpoint_pair_score": float(best["pair_score"]),
                },
            ),
            transform=SimilarityTransform2D(
                angle_degrees=float(best["angle"]),
                reflect_horizontal=bool(best["reflect_horizontal"]),
                scale=float(best["scale"]),
                translation=(float(best["translation"][0]), float(best["translation"][1])),
            ),
            anchor_error=float(best["mean_error"]),
            area_instance=midpoint_anchor.area_instance,
            diagnostics={
                "status": "midpoint_geometry",
                "best_forward_coverage": float(best["coverage"]),
                "joint_shape_coverage": float(best["coverage"]),
                "midpoint_pair_score": float(best["pair_score"]),
                "midpoint_mean_anchor_error": float(best["mean_error"]),
                "midpoint_search_candidates": len(coarse) + len(refined),
                "best_angle": float(best["angle"]),
                "best_reflection": bool(best["reflect_horizontal"]),
                "best_scale": float(best["scale"]),
                "reference_boundary_pixels": int(np.count_nonzero(edge)),
            },
        )

    def _evaluate_assignment(
        self,
        evaluations: list[_AssignmentEvaluation],
        failures: list[dict[str, Any]],
        *,
        assignment: Mapping[str, PlayerMarkerCandidate],
        identities: tuple[str, ...],
        frame: HybridFrame,
        anchors: Mapping[str, PositionAnchor],
        registration: AbsoluteRegistration,
        joint: Mapping[str, Any],
    ) -> None:
        players: dict[str, PlayerLocalization] = {}
        errors: list[float] = []
        for identity in identities:
            candidate = assignment[identity]
            mapped = transform_local_point(
                frame.wall_mask.shape,
                candidate.local_position,
                angle=registration.transform.angle_degrees,
                reflect_horizontal=registration.transform.reflect_horizontal,
                scale=registration.transform.scale,
                translation=registration.transform.translation,
            )
            memory_position = anchors[identity].position
            error = math.dist(mapped, memory_position)
            errors.append(error)
            players[identity] = PlayerLocalization(
                identity=identity,
                candidate_id=candidate.candidate_id,
                screen_position=candidate.local_position,
                memory_position=memory_position,
                mapped_position=mapped,
                anchor_error=error,
                confidence=self._player_confidence(registration.result.confidence, candidate.confidence, error),
                accepted=error <= self.config.max_anchor_error,
            )
        anchor_error_limit = self.config.max_anchor_error
        if joint.get("pair_mode") == "midpoint_geometry":
            anchor_error_limit = min(
                anchor_error_limit,
                self.config.midpoint_max_anchor_error,
            )
        if any(error > anchor_error_limit for error in errors):
            failures.append(
                {
                    "assignment": {identity: assignment[identity].candidate_id for identity in identities},
                    "joint": dict(joint),
                    "reason": "same transform does not explain both memory anchors",
                    "anchor_errors": errors,
                    "anchor_error_limit": anchor_error_limit,
                }
            )
            return
        mapped_delta = (
            players[identities[1]].mapped_position[0] - players[identities[0]].mapped_position[0],
            players[identities[1]].mapped_position[1] - players[identities[0]].mapped_position[1],
        )
        pair_error = math.dist(mapped_delta, joint["native_delta"])
        pair_confidence = math.exp(-pair_error / max(self.config.pair_distance_tolerance, 1e-6))
        profile_indices = [
            player_candidate.color_features.get("profile_index")
            for player_candidate in assignment.values()
        ]
        if all(isinstance(value, int) for value in profile_indices):
            profile_consistency = sum(
                int(profile_indices[index] == index) for index in range(len(identities))
            ) / float(len(identities))
        else:
            profile_consistency = 0.5
        # Keep independent evidence separate.  A sparse minimap frame can
        # have low wall coverage even when both memory anchors and the pair
        # geometry identify one transform exactly.  The previous formula made
        # that coverage a 65% hard proxy for total confidence, so valid dual
        # frames at 0.45--0.60 coverage were rejected.  Anchor identity and
        # pair geometry now carry most of the score, while shape evidence and
        # profile consistency remain explicit diagnostics and tie breakers.
        anchor_quality = sum(
            math.exp(-error / max(self.config.pair_distance_tolerance, 1e-6))
            for error in errors
        ) / float(len(errors))
        shape_quality = min(
            1.0,
            max(0.0, float(registration.result.confidence)),
        )
        score = min(
            1.0,
            anchor_quality * 0.45
            + pair_confidence * 0.25
            + shape_quality * 0.20
            + profile_consistency * 0.10,
        )
        evaluations.append(
            _AssignmentEvaluation(
                assignment=assignment,
                registration=registration,
                players=players,
                score=score,
                mean_anchor_error=float(sum(errors) / len(errors)),
                joint={
                    **joint,
                    "registration_pair_distance_error": float(pair_error),
                    "pair_confidence": float(pair_confidence),
                    "anchor_quality": float(anchor_quality),
                    "shape_quality": float(shape_quality),
                    "profile_consistency": float(profile_consistency),
                },
            )
        )

    def _register_near_joint_estimate(
        self,
        frame: HybridFrame,
        *,
        reference: TerrainReference,
        anchor: PositionAnchor,
        joint: Mapping[str, Any],
    ) -> AbsoluteRegistration | None:
        """Search wall geometry only around the two-anchor estimate."""
        if not isinstance(self.registrar, AnchoredAbsoluteRegistrar):
            return self.registrar.register(frame, reference=reference, anchor=anchor)
        base = self.registrar.config
        angle = float(joint["angle"])
        scale = float(joint["scale"])
        local_config = replace(
            base,
            coarse_angles=(angle,),
            coarse_reflections=(bool(joint["reflect_horizontal"]),),
            coarse_scales=(scale,),
            refine_angle_radius=self.config.joint_angle_radius,
            refine_angle_step=2.0,
            refine_scale_radius=self.config.joint_scale_radius,
            refine_scale_step=max(0.01, self.config.joint_scale_radius / 6.0),
            refine_seed_count=3,
            refine_orientation_seed_count=1,
        )
        direct = self._direct_joint_registration(frame, reference=reference, anchor=anchor, joint=joint)
        if direct is not None and float(direct.diagnostics.get("joint_shape_coverage", 0.0)) >= base.minimum_forward_coverage_when_anchored:
            return direct
        local_registrar = AnchoredAbsoluteRegistrar(local_config)
        registration = local_registrar.register(frame, reference=reference, anchor=anchor)
        if direct is not None:
            if registration is None:
                return direct
            direct_score = float(direct.diagnostics.get("joint_shape_coverage", 0.0))
            existing_score = float(registration.diagnostics.get("best_forward_coverage", 0.0))
            if direct_score >= existing_score:
                return direct
        if registration is not None:
            return registration
        # A sparse first frame can have insufficient wall pixels in the narrow
        # basin. The broad registrar is a correctness fallback, not the normal
        # path, and its diagnostics remain visible to the experiment log.
        return self.registrar.register(frame, reference=reference, anchor=anchor)

    def _direct_joint_registration(
        self,
        frame: HybridFrame,
        *,
        reference: TerrainReference,
        anchor: PositionAnchor,
        joint: Mapping[str, Any],
    ) -> AbsoluteRegistration | None:
        transformed = transform_feature(
            frame.wall_mask,
            frame.local_player,
            angle=float(joint["angle"]),
            reflect_horizontal=bool(joint["reflect_horizontal"]),
            scale=float(joint["scale"]),
        )
        translation = (
            float(anchor.position[0]) - float(transformed.player_position[0]),
            float(anchor.position[1]) - float(transformed.player_position[1]),
        )
        terrain = _reference_match_terrain(reference)
        edge = terrain_edges(terrain)
        distance = cv2.distanceTransform(np.where(edge > 0, 0, 255).astype(np.uint8), cv2.DIST_L2, 3)
        mask = transformed.mask > 0
        x, y = round(translation[0]), round(translation[1])
        x0, y0 = max(0, x), max(0, y)
        x1, y1 = min(edge.shape[1], x + mask.shape[1]), min(edge.shape[0], y + mask.shape[0])
        if x0 >= x1 or y0 >= y1:
            return None
        mx0, my0 = x0 - x, y0 - y
        local_mask = mask[my0 : my0 + y1 - y0, mx0 : mx0 + x1 - x0]
        pixels = int(np.count_nonzero(local_mask))
        if pixels < 8:
            return None
        coverage = float(np.mean(distance[y0:y1, x0:x1][local_mask] <= 4.0))
        confidence = max(0.0, min(1.0, coverage))
        return AbsoluteRegistration(
            result=LocalizationResult(
                position=anchor.position,
                confidence=confidence,
                source="dual_joint_similarity",
                registration_valid=coverage > 0.0,
                metadata={"joint_shape_coverage": coverage},
            ),
            transform=SimilarityTransform2D(
                angle_degrees=float(joint["angle"]),
                reflect_horizontal=bool(joint["reflect_horizontal"]),
                scale=float(joint["scale"]),
                translation=translation,
            ),
            anchor_error=0.0,
            area_instance=anchor.area_instance,
            diagnostics={
                "status": "joint_direct",
                "joint_shape_coverage": coverage,
                "joint_angle": float(joint["angle"]),
                "joint_scale": float(joint["scale"]),
                "reference_boundary_pixels": int(np.count_nonzero(edge)),
            },
        )

    def _player_confidence(
        self,
        registration_confidence: float,
        marker_confidence: float,
        anchor_error: float,
    ) -> float:
        spatial = math.exp(-anchor_error / (2.0 * self.config.max_anchor_error))
        # Registration coverage is evidence quality, not identity quality.
        # Preserve a useful per-player confidence when the anchor is exact but
        # the visible wall fragment is sparse; the pair-level score still
        # gates the complete assignment.
        return min(
            1.0,
            max(0.0, float(registration_confidence)) * 0.20
            + max(0.0, float(marker_confidence)) * 0.20
            + spatial * 0.60,
        )

    def _result(
        self,
        *,
        status: str,
        reason: str,
        primary_registration: AbsoluteRegistration | None = None,
        players: Mapping[str, PlayerLocalization] | None = None,
        diagnostics: Mapping[str, Any] | None = None,
    ) -> DualFirstFrameResult:
        result = DualFirstFrameResult(
            status=status,
            reason=reason,
            primary_registration=primary_registration,
            players=players or {},
            diagnostics=diagnostics or {},
        )
        self.last_diagnostics = result.diagnostics
        return result


__all__ = ["DualFirstFrameConfig", "DualFirstFrameRegistrar"]
