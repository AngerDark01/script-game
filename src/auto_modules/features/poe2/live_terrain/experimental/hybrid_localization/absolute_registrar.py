"""Memory-anchored absolute registration for the PoE2 experiment."""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Any, Mapping, Sequence

import cv2
import numpy as np

from auto_modules.core.localization import LocalizationResult
from auto_modules.core.localization.canonical_wall import canonical_boundary_from_walkable
from auto_modules.features.poe2.live_terrain.terrain_reference import TerrainReference

from .models import (
    AbsoluteRegistration,
    HybridFrame,
    PositionAnchor,
    SimilarityTransform2D,
)
from .similarity_search import (
    SearchCandidate,
    SimilaritySearchConfig,
    clean_feature_mask,
    search_candidates,
    terrain_edges,
    terrain_walkable_mask,
)

@dataclass(frozen=True)
class AnchorLocalProbeInput:
    sample_root: Path | None
    manifest: Mapping[str, Any]
    terrain: np.ndarray
    feature: np.ndarray
    local_player: tuple[float, float]
    anchor_grid: tuple[float, float]


@dataclass(frozen=True)
class AnchoredRegistrationConfig:
    # The 200px minimap sample shows that a 150px coarse / 110px refine
    # window retains the useful wall context without opening a large field of
    # repeated candidates.  Production frames scale these radii from their
    # actual captured size in ``_config_for_frame``.
    crop_radius: int = 150
    refine_crop_radius: int = 110
    capture_reference_size: int = 200
    # The upper minimap band contains dynamic labels/portal overlays.  A
    # 40px exclusion removes their residual edge while retaining the first
    # stable room boundary in the 200px capture used by the current profile.
    top_exclusion_rows: int = 40
    player_clear_radius: int = 22
    # A partial minimap does not form a reliable closed walkable polygon.
    # Memory-anchored registration therefore prioritizes wall geometry.
    similarity_score_weights: tuple[float, float, float, float] = (
        0.55,
        0.25,
        0.15,
        0.05,
    )
    max_anchor_error: float = 80.0
    # The memory position is a direct native-grid observation.  Shape score
    # still selects the orientation/scale basin, while the confirmed anchor
    # carries most of the final confidence for a one-frame registration.
    anchor_weight: float = 0.65
    # The PoE2 composition sets its own acceptance policy.  The generic
    # default remains permissive for synthetic/unit fixtures that exercise
    # geometry gates independently of a calibrated confidence policy.
    minimum_confidence: float = 0.0
    minimum_score: float = 0.50
    # A close, walkable memory anchor is a stronger spatial constraint than
    # the image-only score.  PoE2's calibrated composition may lower this
    # gate for that narrow case without changing generic registrar defaults.
    minimum_score_when_anchored: float | None = None
    minimum_forward_coverage: float = 0.65
    minimum_forward_coverage_when_anchored: float = 0.60
    anchor_acceptance_radius: float = 8.0
    anchor_disambiguation_gap: float = 1.0
    minimum_margin: float = 0.03
    coarse_angles: tuple[float, ...] = tuple(float(value) for value in range(0, 360, 45))
    coarse_reflections: tuple[bool, ...] = (False, True)
    coarse_scales: tuple[float, ...] = tuple(round(0.35 + index * 0.10, 2) for index in range(22))
    refine_angle_radius: float = 12.0
    refine_angle_step: float = 2.0
    refine_scale_radius: float = 0.16
    refine_scale_step: float = 0.02
    refine_seed_count: int = 8
    refine_orientation_seed_count: int = 4
    refine_seed_margin: float = 0.10

    def __post_init__(self) -> None:
        if self.crop_radius < 1 or self.refine_crop_radius < 1:
            raise ValueError("crop radii must be positive")
        if self.capture_reference_size < 1:
            raise ValueError("capture_reference_size must be positive")
        if self.top_exclusion_rows < 0 or self.player_clear_radius < 0:
            raise ValueError("feature exclusion sizes must not be negative")
        if len(self.similarity_score_weights) != 4 or any(
            value < 0.0 for value in self.similarity_score_weights
        ):
            raise ValueError("similarity score weights must contain four non-negative values")
        if not math.isclose(sum(self.similarity_score_weights), 1.0, abs_tol=1e-9):
            raise ValueError("similarity score weights must sum to one")
        if self.max_anchor_error <= 0:
            raise ValueError("max_anchor_error must be positive")
        if not 0.0 < self.minimum_forward_coverage_when_anchored <= 1.0:
            raise ValueError(
                "minimum_forward_coverage_when_anchored must be between zero and one"
            )
        if self.minimum_score_when_anchored is not None and not (
            0.0 <= self.minimum_score_when_anchored <= 1.0
        ):
            raise ValueError("minimum_score_when_anchored must be between zero and one")
        if self.anchor_acceptance_radius <= 0:
            raise ValueError("anchor_acceptance_radius must be positive")
        if self.anchor_disambiguation_gap <= 0:
            raise ValueError("anchor_disambiguation_gap must be positive")
        if not 0.0 <= self.anchor_weight <= 1.0:
            raise ValueError("anchor_weight must be between zero and one")
        if not 0.0 <= self.minimum_confidence <= 1.0:
            raise ValueError("minimum_confidence must be between zero and one")
        if not self.coarse_angles or not self.coarse_reflections or not self.coarse_scales:
            raise ValueError("coarse search variants must not be empty")
        if self.refine_angle_step <= 0 or self.refine_scale_step <= 0:
            raise ValueError("refine steps must be positive")
        if self.refine_seed_count < 1:
            raise ValueError("refine_seed_count must be positive")
        if self.refine_orientation_seed_count < 1:
            raise ValueError("refine_orientation_seed_count must be positive")
        if self.refine_seed_margin < 0.0:
            raise ValueError("refine_seed_margin must not be negative")


@dataclass(frozen=True)
class AnchoredCandidate:
    registration: SearchCandidate
    global_player_position: tuple[float, float]
    anchor_error: float
    anchored_score: float
    basin_angle: float
    basin_reflection: bool
    basin_scale: float | None = None

    def as_dict(self, rank: int | None = None) -> dict[str, Any]:
        payload = self.registration.as_dict(rank)
        payload.update(
            {
                "global_player_position": [
                    float(self.global_player_position[0]),
                    float(self.global_player_position[1]),
                ],
                "anchor_error": float(self.anchor_error),
                "anchored_score": float(self.anchored_score),
                "basin_angle": float(self.basin_angle),
                "basin_reflection": bool(self.basin_reflection),
                "basin_scale": (
                    float(self.basin_scale) if self.basin_scale is not None else None
                ),
            }
        )
        return payload


@dataclass(frozen=True)
class AnchorLocalProbeResult:
    status: str
    reason: str
    anchor_grid: tuple[float, float]
    crop_bounds: tuple[int, int, int, int]
    prepared_feature: np.ndarray
    local_terrain: np.ndarray
    candidates: tuple[AnchoredCandidate, ...]
    best: AnchoredCandidate | None

def crop_terrain_around_anchor(
    terrain: np.ndarray,
    anchor: tuple[float, float],
    radius: int,
) -> tuple[np.ndarray, tuple[int, int, int, int]]:
    array = np.asarray(terrain)
    if array.size == 0 or array.ndim not in (2, 3):
        raise ValueError("terrain must be a non-empty image")
    if radius < 1:
        raise ValueError("crop radius must be positive")
    x, y = float(anchor[0]), float(anchor[1])
    if not math.isfinite(x) or not math.isfinite(y):
        raise ValueError("anchor must be finite")
    center_x = int(round(x))
    center_y = int(round(y))
    x0 = max(0, center_x - int(radius))
    y0 = max(0, center_y - int(radius))
    x1 = min(array.shape[1], center_x + int(radius) + 1)
    y1 = min(array.shape[0], center_y + int(radius) + 1)
    if x0 >= x1 or y0 >= y1:
        raise ValueError("anchor crop does not intersect terrain")
    return np.array(array[y0:y1, x0:x1], copy=True), (x0, y0, x1, y1)


def prepare_local_feature(
    feature: np.ndarray,
    local_player: tuple[float, float],
    *,
    top_exclusion_rows: int,
    player_clear_radius: int,
) -> np.ndarray:
    source = np.asarray(feature)
    if source.size == 0 or source.ndim not in (2, 3):
        raise ValueError("feature must be a non-empty image")
    if source.ndim == 3:
        source = cv2.cvtColor(source, cv2.COLOR_BGR2GRAY)
    prepared = np.where(source > 0, 255, 0).astype(np.uint8)
    excluded_rows = min(prepared.shape[0], max(0, int(top_exclusion_rows)))
    if excluded_rows:
        prepared[:excluded_rows, :] = 0
    radius = max(0, int(player_clear_radius))
    if radius:
        cv2.circle(
            prepared,
            (int(round(local_player[0])), int(round(local_player[1]))),
            radius,
            0,
            thickness=-1,
        )
    cleaned, _components = clean_feature_mask(
        prepared,
        player_position=local_player,
        player_clear_radius=0,
    )
    return cleaned


def _probe_config(
    *,
    angles: Sequence[float],
    reflections: Sequence[bool],
    scales: Sequence[float],
    coarse_factor: float,
    player_hint: tuple[float, float],
    player_radius: float,
    min_spatial_separation: float,
    max_results: int,
    score_weights: tuple[float, float, float, float],
) -> SimilaritySearchConfig:
    return SimilaritySearchConfig(
        angles=tuple(float(value) % 360.0 for value in angles),
        reflect_horizontal=tuple(bool(value) for value in reflections),
        scales=tuple(float(value) for value in scales if float(value) > 0.0),
        coarse_factor=coarse_factor,
        coarse_per_variant=2,
        coarse_keep=48,
        refine_angle_offsets=(0.0,),
        refine_scale_offsets=(0.0,),
        refine_radius=24,
        min_template_edge_pixels=40,
        max_results=max_results,
        min_spatial_separation=min_spatial_separation,
        player_position_hint=player_hint,
        player_position_radius=player_radius,
        score_weights=score_weights,
    )


def _anchored_candidates(
    candidates: Sequence[SearchCandidate],
    *,
    crop_bounds: tuple[int, int, int, int],
    anchor: tuple[float, float],
    max_anchor_error: float,
    anchor_weight: float,
    basin: tuple[float, bool, float] | None = None,
) -> tuple[AnchoredCandidate, ...]:
    x0, y0, _x1, _y1 = crop_bounds
    anchored: list[AnchoredCandidate] = []
    for candidate in candidates:
        global_position = (
            float(candidate.player_position[0]) + x0,
            float(candidate.player_position[1]) + y0,
        )
        error = math.dist(global_position, anchor)
        if error > max_anchor_error:
            continue
        prior = max(0.0, 1.0 - error / max_anchor_error)
        anchored_score = candidate.score * (1.0 - anchor_weight) + prior * anchor_weight
        anchored.append(
            AnchoredCandidate(
                registration=candidate,
                global_player_position=global_position,
                anchor_error=error,
                anchored_score=anchored_score,
                basin_angle=(
                    float(basin[0]) % 360.0 if basin is not None else candidate.angle
                ),
                basin_reflection=(
                    bool(basin[1]) if basin is not None else candidate.reflect_horizontal
                ),
                basin_scale=(
                    float(basin[2]) if basin is not None else candidate.scale
                ),
            )
        )
    anchored.sort(key=lambda item: (item.anchored_score, item.registration.score), reverse=True)
    return tuple(anchored)


def _float_range(center: float, radius: float, step: float) -> tuple[float, ...]:
    if radius <= 0:
        return (float(center),)
    count = int(math.floor((2.0 * radius) / step))
    return tuple(float(center - radius + index * step) for index in range(count + 1))


def _refine_seeds(
    candidates: tuple[AnchoredCandidate, ...],
    config: AnchoredRegistrationConfig,
) -> tuple[AnchoredCandidate, ...]:
    if not candidates:
        return ()
    threshold = candidates[0].anchored_score - config.refine_seed_margin
    groups: dict[tuple[int, bool], list[AnchoredCandidate]] = {}
    for candidate in candidates:
        if candidate.anchored_score < threshold:
            break
        key = (
            int(round(candidate.registration.angle * 10.0)) % 3600,
            candidate.registration.reflect_horizontal,
        )
        if key not in groups and len(groups) >= config.refine_orientation_seed_count:
            continue
        groups.setdefault(key, []).append(candidate)

    selected: list[AnchoredCandidate] = []
    selected_scales: dict[tuple[int, bool], list[float]] = {
        key: [] for key in groups
    }
    consumed: set[int] = set()
    while len(selected) < config.refine_seed_count:
        progressed = False
        for key, items in groups.items():
            for candidate in items:
                identity = id(candidate)
                if identity in consumed:
                    continue
                scale = candidate.registration.scale
                if any(
                    abs(scale - old) <= config.refine_scale_radius
                    for old in selected_scales[key]
                ):
                    consumed.add(identity)
                    continue
                consumed.add(identity)
                selected.append(candidate)
                selected_scales[key].append(scale)
                progressed = True
                break
            if len(selected) >= config.refine_seed_count:
                break
        if not progressed:
            break
    return tuple(selected)


def _deduplicate_anchored_candidates(
    candidates: Sequence[AnchoredCandidate],
    *,
    angle_tolerance: float = 0.5,
    scale_tolerance: float = 0.01,
    position_tolerance: float = 2.0,
) -> tuple[AnchoredCandidate, ...]:
    """Remove the same refined solution emitted by overlapping search seeds.

    Candidates with different orientation basins are deliberately retained even
    when they share a center; those are genuine direction ambiguities. Only
    candidates representing the same transform and nearly identical position
    are duplicates.
    """

    unique: list[AnchoredCandidate] = []
    for candidate in candidates:
        duplicate = False
        for existing in unique:
            angle_delta = abs(
                ((candidate.registration.angle - existing.registration.angle + 180.0) % 360.0)
                - 180.0
            )
            if (
                candidate.registration.reflect_horizontal
                == existing.registration.reflect_horizontal
                and angle_delta <= angle_tolerance
                and abs(candidate.registration.scale - existing.registration.scale)
                <= scale_tolerance
                and math.dist(
                    candidate.global_player_position,
                    existing.global_player_position,
                )
                <= position_tolerance
            ):
                duplicate = True
                break
        if not duplicate:
            unique.append(candidate)
    return tuple(unique)


def _result_status(
    candidates: tuple[AnchoredCandidate, ...],
    config: AnchoredRegistrationConfig,
) -> tuple[str, str]:
    if not candidates:
        return "rejected", "no candidate remained inside the memory-anchor bound"
    best = candidates[0]
    if best.anchored_score < config.minimum_confidence:
        return "rejected", "best candidate confidence is below threshold"
    close_walkable_anchor = (
        best.anchor_error <= config.anchor_acceptance_radius
        and best.registration.player_on_walkable
    )
    minimum_score = config.minimum_score
    if close_walkable_anchor and config.minimum_score_when_anchored is not None:
        minimum_score = config.minimum_score_when_anchored
    if best.registration.score < minimum_score:
        return "rejected", "best candidate score is below the anchored threshold"
    if best.registration.forward_coverage < config.minimum_forward_coverage:
        close_anchor = best.anchor_error <= config.anchor_acceptance_radius
        anchored_coverage_threshold = min(
            config.minimum_forward_coverage_when_anchored,
            config.minimum_forward_coverage,
        )
        anchored_coverage_ok = best.registration.forward_coverage >= anchored_coverage_threshold
        if not (
            close_anchor
            and anchored_coverage_ok
            and best.registration.player_on_walkable
        ):
            return "rejected", "best candidate forward coverage is below threshold"
        # A trusted memory point is a much stronger spatial prior than the
        # approximate wall thickness inferred from one minimap frame. Keep the
        # normal coverage gate for ordinary candidates, but allow a narrow
        # tolerance when the candidate is both close to that anchor and on
        # walkable terrain.
        anchored_reason = "single-frame geometry is consistent with close memory anchor"
    else:
        anchored_reason = "single-frame geometry is consistent with the memory anchor"

    # The memory sample is a direct spatial observation.  When it identifies
    # one candidate clearly enough, prefer that candidate over a slightly
    # higher image-only score from another orientation basin.  This prevents a
    # valid anchor from being rejected as ambiguous merely because wall
    # thickness/scale makes two visual scores close.
    def basin_key(candidate: AnchoredCandidate) -> tuple[int, bool, int]:
        scale = (
            candidate.registration.scale
            if candidate.basin_scale is None
            else candidate.basin_scale
        )
        return (
            int(round(float(candidate.basin_angle) * 1000.0)),
            bool(candidate.basin_reflection),
            int(round(float(scale) * 1000.0)),
        )

    independent = tuple(
        candidate
        for candidate in candidates[1:]
        if basin_key(candidate) != basin_key(best)
    )
    if best.anchor_error <= config.anchor_acceptance_radius:
        next_anchor_error = next(
            (
                candidate.anchor_error
                for candidate in independent
                if candidate.anchor_error <= config.anchor_acceptance_radius
            ),
            None,
        )
        if (
            next_anchor_error is None
            or next_anchor_error - best.anchor_error
            >= config.anchor_disambiguation_gap
        ):
            return "anchored_candidate", anchored_reason
    if independent:
        margin = best.anchored_score - independent[0].anchored_score
        if margin < config.minimum_margin:
            return "ambiguous", "top anchored candidates are not sufficiently separated"
    return "anchored_candidate", anchored_reason


def _prioritize_memory_anchor(
    candidates: Sequence[AnchoredCandidate],
    config: AnchoredRegistrationConfig,
) -> tuple[AnchoredCandidate, ...]:
    """Put the best trusted memory-near candidate first.

    Image score remains the tie-breaker and still gates eligibility.  This
    only changes ordering when the candidate is close to the one-shot memory
    position, on walkable terrain, and meets the normal score/coverage gates.
    """
    items = tuple(candidates)
    threshold = min(
        config.minimum_forward_coverage_when_anchored,
        config.minimum_forward_coverage,
    )
    trusted = [
        candidate
        for candidate in items
        if (
            candidate.anchor_error <= config.anchor_acceptance_radius
            and candidate.registration.score >= config.minimum_score
            and candidate.registration.forward_coverage >= threshold
            and candidate.registration.player_on_walkable
        )
    ]
    if not trusted:
        return items
    nearest = min(
        trusted,
        key=lambda candidate: (candidate.anchor_error, -candidate.anchored_score),
    )
    return (nearest,) + tuple(candidate for candidate in items if candidate is not nearest)


def match_anchor_local(
    probe_input: AnchorLocalProbeInput,
    config: AnchoredRegistrationConfig | None = None,
) -> AnchorLocalProbeResult:
    config = config or AnchoredRegistrationConfig()
    prepared = prepare_local_feature(
        probe_input.feature,
        probe_input.local_player,
        top_exclusion_rows=config.top_exclusion_rows,
        player_clear_radius=config.player_clear_radius,
    )
    coarse_terrain, coarse_bounds = crop_terrain_around_anchor(
        probe_input.terrain,
        probe_input.anchor_grid,
        config.crop_radius,
    )
    coarse_hint = (
        probe_input.anchor_grid[0] - coarse_bounds[0],
        probe_input.anchor_grid[1] - coarse_bounds[1],
    )
    coarse = search_candidates(
        prepared,
        terrain_edges(coarse_terrain),
        player_position=probe_input.local_player,
        terrain_walkable=terrain_walkable_mask(coarse_terrain),
        config=_probe_config(
            angles=config.coarse_angles,
            reflections=config.coarse_reflections,
            scales=config.coarse_scales,
            coarse_factor=0.25,
            player_hint=coarse_hint,
            player_radius=config.max_anchor_error,
            min_spatial_separation=0.0,
            max_results=64,
            score_weights=config.similarity_score_weights,
        ),
    )
    anchored_coarse = _anchored_candidates(
        coarse,
        crop_bounds=coarse_bounds,
        anchor=probe_input.anchor_grid,
        max_anchor_error=config.max_anchor_error,
        anchor_weight=config.anchor_weight,
    )
    if not anchored_coarse:
        return AnchorLocalProbeResult(
            status="rejected",
            reason="no coarse candidate remained inside the memory-anchor bound",
            anchor_grid=probe_input.anchor_grid,
            crop_bounds=coarse_bounds,
            prepared_feature=prepared,
            local_terrain=coarse_terrain,
            candidates=(),
            best=None,
        )

    refine_terrain, refine_bounds = crop_terrain_around_anchor(
        probe_input.terrain,
        probe_input.anchor_grid,
        config.refine_crop_radius,
    )
    refine_hint = (
        probe_input.anchor_grid[0] - refine_bounds[0],
        probe_input.anchor_grid[1] - refine_bounds[1],
    )
    anchored_refined_items: list[AnchoredCandidate] = []
    for seed in _refine_seeds(anchored_coarse, config):
        refined = search_candidates(
            prepared,
            terrain_edges(refine_terrain),
            player_position=probe_input.local_player,
            terrain_walkable=terrain_walkable_mask(refine_terrain),
            config=_probe_config(
                angles=_float_range(
                    seed.registration.angle,
                    config.refine_angle_radius,
                    config.refine_angle_step,
                ),
                reflections=(seed.registration.reflect_horizontal,),
                scales=_float_range(
                    seed.registration.scale,
                    config.refine_scale_radius,
                    config.refine_scale_step,
                ),
                coarse_factor=0.5,
                player_hint=refine_hint,
                player_radius=config.max_anchor_error,
                # Nearby angle/scale variants can project the player within a
                # few pixels of each other.  Keep them until the memory-anchor
                # score is applied; spatial suppression here would discard the
                # better anchored transform using shape score alone.
                min_spatial_separation=0.0,
                max_results=8,
                score_weights=config.similarity_score_weights,
            ),
        )
        anchored_refined_items.extend(
            _anchored_candidates(
                refined,
                crop_bounds=refine_bounds,
                anchor=probe_input.anchor_grid,
                max_anchor_error=config.max_anchor_error,
                anchor_weight=config.anchor_weight,
                basin=(
                    seed.registration.angle,
                    seed.registration.reflect_horizontal,
                    seed.registration.scale,
                ),
            )
        )
    anchored_refined = _deduplicate_anchored_candidates(
        tuple(
            sorted(
                anchored_refined_items,
                key=lambda item: (item.anchored_score, item.registration.score),
                reverse=True,
            )
        )
    )
    candidates = anchored_refined or _deduplicate_anchored_candidates(anchored_coarse)
    candidates = _prioritize_memory_anchor(candidates, config)
    bounds = refine_bounds if anchored_refined else coarse_bounds
    local_terrain = refine_terrain if anchored_refined else coarse_terrain
    status, reason = _result_status(candidates, config)
    return AnchorLocalProbeResult(
        status=status,
        reason=reason,
        anchor_grid=probe_input.anchor_grid,
        crop_bounds=bounds,
        prepared_feature=prepared,
        local_terrain=local_terrain,
        candidates=candidates,
        best=candidates[0] if candidates else None,
    )

AnchorLocalProbeConfig = AnchoredRegistrationConfig


def reference_boundary_layer(reference: TerrainReference) -> np.ndarray:
    """Derive the thin walkable boundary used by visual wall matching."""
    return canonical_boundary_from_walkable(
        reference.walkable_mask,
        reference.explored_map,
    )


def _terrain_from_reference(reference: TerrainReference) -> np.ndarray:
    known = np.asarray(reference.explored_map) > 0
    walkable = np.asarray(reference.walkable_mask, dtype=bool) & known
    boundary = reference_boundary_layer(reference) > 0
    terrain = np.zeros(reference.shape, dtype=np.uint8)
    terrain[walkable] = 60
    terrain[boundary] = 235
    return terrain


def match_anchor_local_arrays(
    *,
    terrain: np.ndarray,
    feature: np.ndarray,
    local_player: tuple[float, float],
    anchor: tuple[float, float],
    config: AnchoredRegistrationConfig | None = None,
) -> AnchorLocalProbeResult:
    return match_anchor_local(
        AnchorLocalProbeInput(
            sample_root=None,
            manifest={},
            terrain=np.asarray(terrain),
            feature=np.asarray(feature),
            local_player=local_player,
            anchor_grid=anchor,
        ),
        config,
    )


class AnchoredAbsoluteRegistrar:
    def __init__(self, config: AnchoredRegistrationConfig | None = None) -> None:
        self.config = config or AnchoredRegistrationConfig()
        self.last_diagnostics: Mapping[str, Any] = {}

    def _config_for_frame(
        self,
        frame: HybridFrame,
        config: AnchoredRegistrationConfig,
    ) -> AnchoredRegistrationConfig:
        """Scale local terrain windows to the actual captured minimap size.

        ``HybridFrame.from_evidence`` records ``capture_size`` only for real
        monitor captures.  Hand-built test frames and offline probes keep the
        explicitly supplied radii unchanged.  The reference size is 200px,
        matching the calibration samples used to choose the default 150/110
        windows.
        """
        if "capture_size" not in frame.diagnostics:
            return config
        height, width = frame.wall_mask.shape
        actual_size = max(int(height), int(width))
        if actual_size < 1:
            return config
        factor = actual_size / float(config.capture_reference_size)
        if abs(factor - 1.0) < 1e-9:
            return config
        return replace(
            config,
            crop_radius=max(1, int(round(config.crop_radius * factor))),
            refine_crop_radius=max(1, int(round(config.refine_crop_radius * factor))),
            top_exclusion_rows=max(0, int(round(config.top_exclusion_rows * factor))),
        )

    def register(
        self,
        frame: HybridFrame,
        *,
        reference: TerrainReference,
        anchor: PositionAnchor,
        prior: AbsoluteRegistration | None = None,
    ) -> AbsoluteRegistration | None:
        self.last_diagnostics = {}
        reference_instance = str(reference.metadata.get("instance_id") or "")
        if reference_instance and reference_instance != anchor.area_instance:
            self.last_diagnostics = {
                "status": "rejected",
                "reason": "reference and memory-anchor instances do not match",
                "reference_instance": reference_instance,
                "anchor_instance": anchor.area_instance,
            }
            return None
        if prior is not None and prior.area_instance != anchor.area_instance:
            self.last_diagnostics = {
                "status": "rejected",
                "reason": "prior and memory-anchor instances do not match",
                "prior_instance": prior.area_instance,
                "anchor_instance": anchor.area_instance,
            }
            return None

        frame_config = self._config_for_frame(frame, self.config)
        if prior is None:
            attempts = (("full_similarity", frame_config),)
        else:
            locked_config = replace(
                frame_config,
                coarse_angles=(prior.transform.angle_degrees,),
                coarse_reflections=(prior.transform.reflect_horizontal,),
                coarse_scales=(prior.transform.scale,),
                refine_angle_radius=0.0,
                refine_scale_radius=0.0,
                refine_seed_count=1,
            )
            # A recovery normally keeps the last known direction for speed,
            # but a changed/partially visible frame can invalidate that local
            # basin.  Retry the same memory read with the full orientation
            # search before declaring global recovery unusable.
            attempts = (
                ("translation_only", locked_config),
                ("full_similarity_recovery", frame_config),
            )

        terrain = _terrain_from_reference(reference)
        probe = None
        config = self.config
        search_mode = "full_similarity"
        for search_mode, config in attempts:
            probe = match_anchor_local_arrays(
                terrain=terrain,
                feature=frame.wall_mask,
                local_player=frame.local_player,
                anchor=anchor.position,
                config=config,
            )
            if probe.status == "anchored_candidate" and probe.best is not None:
                break
        assert probe is not None
        diagnostics: dict[str, Any] = {
            "status": probe.status,
            "reason": probe.reason,
            "search_mode": search_mode,
            "attempt_count": len(attempts),
            "coarse_variant_count": (
                len(config.coarse_angles)
                * len(config.coarse_reflections)
                * len(config.coarse_scales)
            ),
            "candidate_count": len(probe.candidates),
            "minimum_confidence": config.minimum_confidence,
            "minimum_score": config.minimum_score,
            "minimum_score_when_anchored": config.minimum_score_when_anchored,
            "minimum_forward_coverage": config.minimum_forward_coverage,
            "minimum_forward_coverage_when_anchored": (
                config.minimum_forward_coverage_when_anchored
            ),
            "anchor_acceptance_radius": config.anchor_acceptance_radius,
            "anchor_disambiguation_gap": config.anchor_disambiguation_gap,
            "capture_size": max(frame.wall_mask.shape),
            "crop_radius": config.crop_radius,
            "refine_crop_radius": config.refine_crop_radius,
            "top_exclusion_rows": config.top_exclusion_rows,
            "player_clear_radius": config.player_clear_radius,
        }
        if probe.best is not None:
            best = probe.best
            diagnostics.update(
                {
                    "best_score": best.registration.score,
                    "best_anchored_score": best.anchored_score,
                    "confidence": min(1.0, max(0.0, float(best.anchored_score))),
                    "best_forward_coverage": best.registration.forward_coverage,
                    "best_angle": best.registration.angle,
                    "best_reflection": best.registration.reflect_horizontal,
                    "best_scale": best.registration.scale,
                    "best_anchor_error": best.anchor_error,
                    "best_player_on_walkable": best.registration.player_on_walkable,
                }
            )
        self.last_diagnostics = diagnostics
        if probe.status != "anchored_candidate" or probe.best is None:
            return None

        best = probe.best
        top_left = (
            float(probe.crop_bounds[0] + best.registration.top_left[0]),
            float(probe.crop_bounds[1] + best.registration.top_left[1]),
        )
        confidence = min(1.0, max(0.0, float(best.anchored_score)))
        return AbsoluteRegistration(
            result=LocalizationResult(
                position=best.global_player_position,
                confidence=confidence,
                source="anchored_absolute",
                registration_valid=True,
                metadata={"anchor_error": best.anchor_error, "status": probe.status},
            ),
            transform=SimilarityTransform2D(
                angle_degrees=best.registration.angle,
                reflect_horizontal=best.registration.reflect_horizontal,
                scale=best.registration.scale,
                translation=top_left,
            ),
            anchor_error=best.anchor_error,
            area_instance=anchor.area_instance,
            diagnostics=diagnostics,
        )


__all__ = [
    "AnchorLocalProbeConfig",
    "AnchorLocalProbeInput",
    "AnchorLocalProbeResult",
    "AnchoredAbsoluteRegistrar",
    "AnchoredCandidate",
    "AnchoredRegistrationConfig",
    "crop_terrain_around_anchor",
    "match_anchor_local",
    "match_anchor_local_arrays",
    "prepare_local_feature",
    "reference_boundary_layer",
]
