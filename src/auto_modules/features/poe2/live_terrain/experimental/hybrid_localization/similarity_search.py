"""Pure similarity-transform search used by PoE2 localization experiments."""

from __future__ import annotations

import logging
import math
from dataclasses import asdict, dataclass
from typing import Any

import cv2
import numpy as np


LOGGER = logging.getLogger("poe2.hybrid_localization.similarity_search")

@dataclass(frozen=True)
class SimilaritySearchConfig:
    angles: tuple[float, ...] = tuple(float(value) for value in range(0, 360, 45))
    reflect_horizontal: tuple[bool, ...] = (False, True)
    scales: tuple[float, ...] = tuple(round(0.35 + index * 0.10, 2) for index in range(22))
    coarse_factor: float = 0.25
    coarse_per_variant: int = 2
    coarse_keep: int = 24
    refine_angle_offsets: tuple[float, ...] = (-4.0, 0.0, 4.0)
    refine_scale_offsets: tuple[float, ...] = (-0.04, 0.0, 0.04)
    refine_radius: int = 48
    match_tolerance: float = 3.0
    reverse_tolerance: float = 3.0
    min_component_area: int = 20
    min_component_span: int = 24
    player_clear_radius: int = 22
    terrain_border_clear: int = 2
    min_template_edge_pixels: int = 120
    acceptance_score: float = 0.72
    acceptance_margin: float = 0.05
    max_results: int = 10
    min_spatial_separation: float = 42.0
    player_position_hint: tuple[float, float] | None = None
    player_position_radius: float | None = None
    coarse_player_walkable_radius: int = 2
    # forward coverage, Chamfer distance, reverse coverage, walkable fill
    score_weights: tuple[float, float, float, float] = (0.42, 0.18, 0.12, 0.28)

    def __post_init__(self) -> None:
        if not self.angles or not self.reflect_horizontal or not self.scales:
            raise ValueError("angles, reflections, and scales must not be empty")
        if not 0.05 <= self.coarse_factor <= 1.0:
            raise ValueError("coarse_factor must be between 0.05 and 1.0")
        if min(self.scales) <= 0.0:
            raise ValueError("scales must be positive")
        if self.match_tolerance <= 0.0 or self.reverse_tolerance <= 0.0:
            raise ValueError("Chamfer tolerances must be positive")
        if (self.player_position_hint is None) != (self.player_position_radius is None):
            raise ValueError("player position hint and radius must be provided together")
        if self.player_position_hint is not None:
            if len(self.player_position_hint) != 2 or not all(
                math.isfinite(float(value)) for value in self.player_position_hint
            ):
                raise ValueError("player position hint must contain two finite values")
            radius = self.player_position_radius
            if radius is None or not math.isfinite(float(radius)) or float(radius) <= 0.0:
                raise ValueError("player position radius must be positive and finite")
        if int(self.coarse_player_walkable_radius) < 0:
            raise ValueError("coarse player walkable radius must not be negative")
        if len(self.score_weights) != 4 or any(value < 0.0 for value in self.score_weights):
            raise ValueError("score weights must contain four non-negative values")
        if not math.isclose(sum(self.score_weights), 1.0, abs_tol=1e-9):
            raise ValueError("score weights must sum to one")

@dataclass(frozen=True)
class SearchCandidate:
    angle: float
    reflect_horizontal: bool
    scale: float
    top_left: tuple[int, int]
    player_position: tuple[float, float]
    mean_distance: float
    forward_coverage: float
    reverse_coverage: float
    walkable_coverage: float
    player_on_walkable: bool
    score: float
    edge_pixels: int

    def as_dict(self, rank: int | None = None) -> dict[str, Any]:
        result = asdict(self)
        result["top_left"] = list(self.top_left)
        result["player_position"] = [round(value, 3) for value in self.player_position]
        if rank is not None:
            result["rank"] = rank
        return result


@dataclass(frozen=True)
class _TransformedFeature:
    mask: np.ndarray
    player_position: tuple[float, float]


@dataclass(frozen=True)
class _CoarseCandidate:
    angle: float
    reflect_horizontal: bool
    scale: float
    top_left: tuple[float, float]
    mean_distance: float
    player_on_walkable: bool

def _binary_mask(value: np.ndarray) -> np.ndarray:
    array = np.asarray(value)
    if array.ndim == 3:
        array = cv2.cvtColor(array, cv2.COLOR_BGR2GRAY)
    if array.ndim != 2 or array.size == 0:
        raise ValueError("feature mask must be a non-empty 2D image")
    return np.where(array > 0, 255, 0).astype(np.uint8)


def terrain_edges(terrain: np.ndarray, border_clear: int = 2) -> np.ndarray:
    gray = cv2.cvtColor(terrain, cv2.COLOR_BGR2GRAY) if terrain.ndim == 3 else terrain
    edge = np.where(gray >= 180, 255, 0).astype(np.uint8)
    width = max(0, int(border_clear))
    if width:
        edge[:width, :] = 0
        edge[-width:, :] = 0
        edge[:, :width] = 0
        edge[:, -width:] = 0
    return edge


def terrain_walkable_mask(terrain: np.ndarray) -> np.ndarray:
    gray = cv2.cvtColor(terrain, cv2.COLOR_BGR2GRAY) if terrain.ndim == 3 else terrain
    return np.where((gray >= 20) & (gray < 180), 255, 0).astype(np.uint8)


def local_walkable_region(
    feature: np.ndarray,
    player_position: tuple[float, float],
) -> np.ndarray:
    """Recover the visible walkable side of the local boundary from the player seed."""
    edge = _binary_mask(feature)
    barrier = cv2.dilate(edge, np.ones((3, 3), dtype=np.uint8)) > 0
    barrier[0, :] = True
    barrier[-1, :] = True
    barrier[:, 0] = True
    barrier[:, -1] = True
    free = np.where(barrier, 0, 1).astype(np.uint8)
    _count, labels, _stats, _centroids = cv2.connectedComponentsWithStats(free, connectivity=8)
    x = min(max(0, int(round(player_position[0]))), edge.shape[1] - 1)
    y = min(max(0, int(round(player_position[1]))), edge.shape[0] - 1)
    label = int(labels[y, x])
    if label == 0:
        return np.zeros_like(edge)
    return np.where(labels == label, 255, 0).astype(np.uint8)


def clean_feature_mask(
    feature: np.ndarray,
    *,
    player_position: tuple[float, float],
    player_clear_radius: int = 22,
    min_component_area: int = 20,
    min_component_span: int = 24,
) -> tuple[np.ndarray, list[dict[str, Any]]]:
    """Remove compact non-map components while preserving clipped map walls."""
    mask = _binary_mask(feature)
    if player_clear_radius > 0:
        cv2.circle(
            mask,
            (int(round(player_position[0])), int(round(player_position[1]))),
            int(player_clear_radius),
            0,
            thickness=-1,
        )
    count, labels, stats, _centroids = cv2.connectedComponentsWithStats(mask, connectivity=8)
    height, width = mask.shape
    cleaned = np.zeros_like(mask)
    diagnostics: list[dict[str, Any]] = []
    for label in range(1, count):
        x = int(stats[label, cv2.CC_STAT_LEFT])
        y = int(stats[label, cv2.CC_STAT_TOP])
        component_width = int(stats[label, cv2.CC_STAT_WIDTH])
        component_height = int(stats[label, cv2.CC_STAT_HEIGHT])
        area = int(stats[label, cv2.CC_STAT_AREA])
        touches_border = bool(
            x == 0
            or y == 0
            or x + component_width >= width
            or y + component_height >= height
        )
        span = max(component_width, component_height)
        keep = bool(
            area >= int(min_component_area)
            and (touches_border or span >= int(min_component_span))
        )
        if keep:
            cleaned[labels == label] = 255
        diagnostics.append(
            {
                "label": label,
                "area": area,
                "bbox": [x, y, component_width, component_height],
                "touches_border": touches_border,
                "kept": keep,
            }
        )
    diagnostics.sort(key=lambda item: int(item["area"]), reverse=True)
    return cleaned, diagnostics


def _rotate_bound(
    mask: np.ndarray,
    point: tuple[float, float],
    angle: float,
) -> _TransformedFeature:
    height, width = mask.shape
    center = ((width - 1) / 2.0, (height - 1) / 2.0)
    matrix = cv2.getRotationMatrix2D(center, float(angle), 1.0)
    cosine = abs(float(matrix[0, 0]))
    sine = abs(float(matrix[0, 1]))
    out_width = max(1, int(math.ceil(height * sine + width * cosine)))
    out_height = max(1, int(math.ceil(height * cosine + width * sine)))
    matrix[0, 2] += (out_width - 1) / 2.0 - center[0]
    matrix[1, 2] += (out_height - 1) / 2.0 - center[1]
    rotated = cv2.warpAffine(
        mask,
        matrix,
        (out_width, out_height),
        flags=cv2.INTER_NEAREST,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=0,
    )
    vector = matrix @ np.array([float(point[0]), float(point[1]), 1.0], dtype=np.float64)
    return _TransformedFeature(_binary_mask(rotated), (float(vector[0]), float(vector[1])))


def transform_feature(
    feature: np.ndarray,
    player_position: tuple[float, float],
    *,
    angle: float,
    reflect_horizontal: bool,
    scale: float,
) -> _TransformedFeature:
    mask = _binary_mask(feature)
    point = (float(player_position[0]), float(player_position[1]))
    if reflect_horizontal:
        mask = cv2.flip(mask, 1)
        point = (float(mask.shape[1] - 1) - point[0], point[1])
    rotated = _rotate_bound(mask, point, angle)
    out_width = max(1, int(round(rotated.mask.shape[1] * float(scale))))
    out_height = max(1, int(round(rotated.mask.shape[0] * float(scale))))
    resized = cv2.resize(rotated.mask, (out_width, out_height), interpolation=cv2.INTER_NEAREST)
    return _TransformedFeature(
        _binary_mask(resized),
        (rotated.player_position[0] * scale, rotated.player_position[1] * scale),
    )


def transform_local_point(
    feature_shape: tuple[int, int],
    point: tuple[float, float],
    *,
    angle: float,
    reflect_horizontal: bool,
    scale: float,
    translation: tuple[float, float] = (0.0, 0.0),
) -> tuple[float, float]:
    """Map a point through the same transform used by ``transform_feature``.

    The minimap registration stores only the transformed template's top-left
    corner.  This helper exposes the corresponding point mapping for a second
    marker without creating a synthetic image or maintaining a second rotation
    convention in an experiment layer.
    """
    if len(feature_shape) != 2:
        raise ValueError("feature_shape must contain height and width")
    height, width = (int(feature_shape[0]), int(feature_shape[1]))
    if height <= 0 or width <= 0:
        raise ValueError("feature_shape must be positive")
    if len(point) != 2 or len(translation) != 2:
        raise ValueError("point and translation must contain two values")
    scale_value = float(scale)
    if not math.isfinite(scale_value) or scale_value <= 0.0:
        raise ValueError("scale must be positive and finite")

    x_value, y_value = float(point[0]), float(point[1])
    if not math.isfinite(x_value) or not math.isfinite(y_value):
        raise ValueError("point must contain finite values")
    if reflect_horizontal:
        x_value = float(width - 1) - x_value

    center = ((width - 1) / 2.0, (height - 1) / 2.0)
    matrix = cv2.getRotationMatrix2D(center, float(angle), 1.0)
    cosine = abs(float(matrix[0, 0]))
    sine = abs(float(matrix[0, 1]))
    out_width = max(1, int(math.ceil(height * sine + width * cosine)))
    out_height = max(1, int(math.ceil(height * cosine + width * sine)))
    matrix[0, 2] += (out_width - 1) / 2.0 - center[0]
    matrix[1, 2] += (out_height - 1) / 2.0 - center[1]
    rotated = matrix @ np.array([x_value, y_value, 1.0], dtype=np.float64)
    offset = np.asarray(translation, dtype=np.float64)
    return (
        float(rotated[0] * scale_value + offset[0]),
        float(rotated[1] * scale_value + offset[1]),
    )


def inverse_transform_local_point(
    feature_shape: tuple[int, int],
    native_point: tuple[float, float],
    *,
    angle: float,
    reflect_horizontal: bool,
    scale: float,
    translation: tuple[float, float] = (0.0, 0.0),
) -> tuple[float, float]:
    """Invert the exact affine mapping used by transform_local_point."""
    kwargs = dict(angle=angle, reflect_horizontal=reflect_horizontal,
                  scale=scale, translation=translation)
    origin = np.asarray(transform_local_point(feature_shape, (0.0, 0.0), **kwargs))
    axis_x = np.asarray(transform_local_point(feature_shape, (1.0, 0.0), **kwargs)) - origin
    axis_y = np.asarray(transform_local_point(feature_shape, (0.0, 1.0), **kwargs)) - origin
    vector = np.linalg.solve(
        np.column_stack((axis_x, axis_y)), np.asarray(native_point, dtype=np.float64) - origin,
    )
    return float(vector[0]), float(vector[1])


def _distance_field(edge: np.ndarray) -> np.ndarray:
    binary = _binary_mask(edge)
    return cv2.distanceTransform(np.where(binary > 0, 0, 255).astype(np.uint8), cv2.DIST_L2, 3)


def _mean_distance_map(distance: np.ndarray, template: np.ndarray) -> np.ndarray:
    weights = (template > 0).astype(np.float32)
    count = int(np.count_nonzero(weights))
    if count < 8:
        raise ValueError("feature template must contain at least 8 edge pixels")
    if template.shape[0] > distance.shape[0] or template.shape[1] > distance.shape[1]:
        raise ValueError("feature template is larger than terrain")
    return cv2.matchTemplate(distance.astype(np.float32), weights, cv2.TM_CCORR) / float(count)


def _local_minima(
    values: np.ndarray,
    *,
    count: int,
    suppression_radius: int,
) -> list[tuple[float, tuple[int, int]]]:
    work = np.array(values, dtype=np.float32, copy=True)
    result: list[tuple[float, tuple[int, int]]] = []
    for _ in range(max(1, int(count))):
        min_value, _max_value, min_location, _max_location = cv2.minMaxLoc(work)
        if not np.isfinite(min_value):
            break
        result.append((float(min_value), (int(min_location[0]), int(min_location[1]))))
        x, y = min_location
        radius = max(1, int(suppression_radius))
        work[max(0, y - radius) : y + radius + 1, max(0, x - radius) : x + radius + 1] = np.inf
    return result


def _mask_outside_player_hint(
    values: np.ndarray,
    *,
    top_left_origin: tuple[float, float],
    transformed_player: tuple[float, float],
    player_hint: tuple[float, float] | None,
    player_radius: float | None,
) -> np.ndarray:
    if player_hint is None or player_radius is None:
        return values
    height, width = values.shape
    xs = (
        np.arange(width, dtype=np.float32)
        + float(top_left_origin[0])
        + float(transformed_player[0])
        - float(player_hint[0])
    )
    ys = (
        np.arange(height, dtype=np.float32)
        + float(top_left_origin[1])
        + float(transformed_player[1])
        - float(player_hint[1])
    )
    allowed = ys[:, None] * ys[:, None] + xs[None, :] * xs[None, :] <= float(
        player_radius
    ) ** 2
    masked = np.array(values, dtype=np.float32, copy=True)
    masked[~allowed] = np.inf
    return masked


def _point_is_walkable(
    walkable: np.ndarray,
    point: tuple[float, float],
    *,
    radius: int,
) -> bool:
    x = int(round(float(point[0])))
    y = int(round(float(point[1])))
    margin = max(0, int(radius))
    x0 = max(0, x - margin)
    y0 = max(0, y - margin)
    x1 = min(walkable.shape[1], x + margin + 1)
    y1 = min(walkable.shape[0], y + margin + 1)
    return bool(x0 < x1 and y0 < y1 and np.any(walkable[y0:y1, x0:x1] > 0))


def _coarse_search(
    feature: np.ndarray,
    terrain_edge: np.ndarray,
    player_position: tuple[float, float],
    config: SimilaritySearchConfig,
    terrain_walkable: np.ndarray | None = None,
) -> list[_CoarseCandidate]:
    factor = float(config.coarse_factor)
    coarse_width = max(1, int(round(terrain_edge.shape[1] * factor)))
    coarse_height = max(1, int(round(terrain_edge.shape[0] * factor)))
    coarse_terrain = cv2.resize(
        terrain_edge,
        (coarse_width, coarse_height),
        interpolation=cv2.INTER_AREA,
    )
    coarse_terrain = np.where(coarse_terrain > 32, 255, 0).astype(np.uint8)
    distance = _distance_field(coarse_terrain)
    candidates: list[_CoarseCandidate] = []
    for reflect in config.reflect_horizontal:
        for angle in config.angles:
            for scale in config.scales:
                transformed = transform_feature(
                    feature,
                    player_position,
                    angle=angle,
                    reflect_horizontal=reflect,
                    scale=scale * factor,
                )
                if min(transformed.mask.shape) < 3:
                    continue
                try:
                    values = _mean_distance_map(distance, transformed.mask)
                except ValueError:
                    continue
                hint = (
                    (
                        float(config.player_position_hint[0]) * factor,
                        float(config.player_position_hint[1]) * factor,
                    )
                    if config.player_position_hint is not None
                    else None
                )
                radius_hint = (
                    float(config.player_position_radius) * factor
                    if config.player_position_radius is not None
                    else None
                )
                values = _mask_outside_player_hint(
                    values,
                    top_left_origin=(0.0, 0.0),
                    transformed_player=transformed.player_position,
                    player_hint=hint,
                    player_radius=radius_hint,
                )
                radius = max(3, min(transformed.mask.shape) // 3)
                for mean_distance, top_left in _local_minima(
                    values,
                    count=config.coarse_per_variant,
                    suppression_radius=radius,
                ):
                    full_top_left = (top_left[0] / factor, top_left[1] / factor)
                    full_player = (
                        full_top_left[0] + transformed.player_position[0] / factor,
                        full_top_left[1] + transformed.player_position[1] / factor,
                    )
                    player_on_walkable = terrain_walkable is None or _point_is_walkable(
                        terrain_walkable,
                        full_player,
                        radius=config.coarse_player_walkable_radius,
                    )
                    candidates.append(
                        _CoarseCandidate(
                            angle=float(angle),
                            reflect_horizontal=bool(reflect),
                            scale=float(scale),
                            top_left=full_top_left,
                            mean_distance=mean_distance / factor,
                            player_on_walkable=player_on_walkable,
                        )
                    )
    candidates.sort(key=lambda item: (not item.player_on_walkable, item.mean_distance))
    return candidates[: max(1, int(config.coarse_keep))]


def _evaluate_candidate(
    transformed: _TransformedFeature,
    transformed_walkable: np.ndarray,
    terrain_edge: np.ndarray,
    terrain_distance: np.ndarray,
    terrain_walkable: np.ndarray | None,
    predicted_top_left: tuple[float, float],
    config: SimilaritySearchConfig,
    *,
    angle: float,
    reflect_horizontal: bool,
    scale: float,
) -> SearchCandidate | None:
    template = transformed.mask
    height, width = template.shape
    template_edge_pixels = int(np.count_nonzero(template))
    if template_edge_pixels < int(config.min_template_edge_pixels):
        return None
    max_x = terrain_edge.shape[1] - width
    max_y = terrain_edge.shape[0] - height
    if max_x < 0 or max_y < 0:
        return None
    predicted_x = int(round(predicted_top_left[0]))
    predicted_y = int(round(predicted_top_left[1]))
    radius = max(0, int(config.refine_radius))
    x0 = max(0, predicted_x - radius)
    y0 = max(0, predicted_y - radius)
    x1 = min(max_x, predicted_x + radius)
    y1 = min(max_y, predicted_y + radius)
    search = terrain_distance[y0 : y1 + height + 1, x0 : x1 + width + 1]
    if search.shape[0] < height or search.shape[1] < width:
        return None
    values = _mean_distance_map(search, template)
    values = _mask_outside_player_hint(
        values,
        top_left_origin=(float(x0), float(y0)),
        transformed_player=transformed.player_position,
        player_hint=config.player_position_hint,
        player_radius=config.player_position_radius,
    )
    if not np.isfinite(values).any():
        return None
    _minimum, location = _local_minima(values, count=1, suppression_radius=1)[0]
    top_left = (x0 + location[0], y0 + location[1])
    distance_patch = terrain_distance[
        top_left[1] : top_left[1] + height,
        top_left[0] : top_left[0] + width,
    ]
    edge_points = template > 0
    distances = distance_patch[edge_points]
    if distances.size < 8:
        return None
    mean_distance = float(distances.mean())
    forward = float(np.mean(distances <= float(config.match_tolerance)))

    terrain_patch = terrain_edge[
        top_left[1] : top_left[1] + height,
        top_left[0] : top_left[0] + width,
    ]
    local_distance = _distance_field(template)
    terrain_points = terrain_patch > 0
    reverse = (
        float(np.mean(local_distance[terrain_points] <= float(config.reverse_tolerance)))
        if int(np.count_nonzero(terrain_points))
        else 0.0
    )
    walkable_coverage = 1.0
    player_on_walkable = True
    if terrain_walkable is not None:
        local_walkable = transformed_walkable > 0
        walkable_patch = terrain_walkable[
            top_left[1] : top_left[1] + height,
            top_left[0] : top_left[0] + width,
        ] > 0
        walkable_coverage = (
            float(np.mean(walkable_patch[local_walkable]))
            if int(np.count_nonzero(local_walkable))
            else 0.0
        )
        player_x = int(round(top_left[0] + transformed.player_position[0]))
        player_y = int(round(top_left[1] + transformed.player_position[1]))
        player_on_walkable = bool(
            0 <= player_x < terrain_walkable.shape[1]
            and 0 <= player_y < terrain_walkable.shape[0]
            and terrain_walkable[player_y, player_x] > 0
        )
    distance_score = math.exp(-mean_distance / float(config.match_tolerance))
    forward_weight, distance_weight, reverse_weight, walkable_weight = config.score_weights
    score = (
        forward_weight * forward
        + distance_weight * distance_score
        + reverse_weight * reverse
        + walkable_weight * walkable_coverage
    )
    if not player_on_walkable:
        score *= 0.35
    player = (
        float(top_left[0]) + transformed.player_position[0],
        float(top_left[1]) + transformed.player_position[1],
    )
    return SearchCandidate(
        angle=float(angle) % 360.0,
        reflect_horizontal=bool(reflect_horizontal),
        scale=float(scale),
        top_left=top_left,
        player_position=player,
        mean_distance=mean_distance,
        forward_coverage=forward,
        reverse_coverage=reverse,
        walkable_coverage=walkable_coverage,
        player_on_walkable=player_on_walkable,
        score=float(score),
        edge_pixels=int(distances.size),
    )


def search_candidates(
    feature: np.ndarray,
    terrain_edge: np.ndarray,
    *,
    player_position: tuple[float, float],
    terrain_walkable: np.ndarray | None = None,
    config: SimilaritySearchConfig | None = None,
) -> list[SearchCandidate]:
    config = config or SimilaritySearchConfig()
    feature = _binary_mask(feature)
    terrain_edge = _binary_mask(terrain_edge)
    normalized_walkable = (
        _binary_mask(terrain_walkable) if terrain_walkable is not None else None
    )
    if normalized_walkable is not None:
        if normalized_walkable.shape != terrain_edge.shape:
            raise ValueError("terrain_walkable must match terrain_edge shape")
    if int(np.count_nonzero(feature)) < 8:
        raise ValueError("cleaned feature contains fewer than 8 edge pixels")
    if int(np.count_nonzero(terrain_edge)) < 8:
        raise ValueError("terrain contains fewer than 8 edge pixels")

    LOGGER.info(
        "step=search.coarse variants=%s scales=%s terrain=%sx%s feature=%sx%s",
        len(config.angles) * len(config.reflect_horizontal),
        len(config.scales),
        terrain_edge.shape[1],
        terrain_edge.shape[0],
        feature.shape[1],
        feature.shape[0],
    )
    coarse = _coarse_search(
        feature,
        terrain_edge,
        player_position,
        config,
        terrain_walkable=normalized_walkable,
    )
    terrain_distance = _distance_field(terrain_edge)
    local_walkable = local_walkable_region(feature, player_position)
    refined: list[SearchCandidate] = []
    seen_variants: set[tuple[int, bool, int, int, int]] = set()
    for seed in coarse:
        for angle_offset in config.refine_angle_offsets:
            for scale_offset in config.refine_scale_offsets:
                angle = (seed.angle + angle_offset) % 360.0
                scale = seed.scale + scale_offset
                if scale <= 0.0:
                    continue
                variant_key = (
                    int(round(angle * 10)),
                    seed.reflect_horizontal,
                    int(round(scale * 1000)),
                    int(round(seed.top_left[0] / 8.0)),
                    int(round(seed.top_left[1] / 8.0)),
                )
                if variant_key in seen_variants:
                    continue
                seen_variants.add(variant_key)
                transformed = transform_feature(
                    feature,
                    player_position,
                    angle=angle,
                    reflect_horizontal=seed.reflect_horizontal,
                    scale=scale,
                )
                transformed_walkable = transform_feature(
                    local_walkable,
                    player_position,
                    angle=angle,
                    reflect_horizontal=seed.reflect_horizontal,
                    scale=scale,
                ).mask
                candidate = _evaluate_candidate(
                    transformed,
                    transformed_walkable,
                    terrain_edge,
                    terrain_distance,
                    normalized_walkable,
                    seed.top_left,
                    config,
                    angle=angle,
                    reflect_horizontal=seed.reflect_horizontal,
                    scale=scale,
                )
                if candidate is not None:
                    refined.append(candidate)
    refined.sort(key=lambda item: (-item.score, item.mean_distance))

    distinct: list[SearchCandidate] = []
    for candidate in refined:
        if all(
            math.dist(candidate.player_position, old.player_position)
            >= float(config.min_spatial_separation)
            for old in distinct
        ):
            distinct.append(candidate)
            if len(distinct) >= int(config.max_results):
                break
    LOGGER.info("step=search.complete refined=%s distinct=%s", len(refined), len(distinct))
    return distinct

__all__ = [
    "SearchCandidate",
    "SimilaritySearchConfig",
    "clean_feature_mask",
    "local_walkable_region",
    "search_candidates",
    "terrain_edges",
    "terrain_walkable_mask",
    "transform_local_point",
    "inverse_transform_local_point",
    "transform_feature",
]
