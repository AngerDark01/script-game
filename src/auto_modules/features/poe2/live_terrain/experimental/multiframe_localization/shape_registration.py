"""Robust, thickness-tolerant shape scoring for experiment candidates."""

from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
import math

import cv2
import numpy as np

from auto_modules.features.poe2.live_terrain.experimental.hybrid_localization.models import SimilarityTransform2D


@dataclass(frozen=True)
class ShapeScore:
    forward_error: float
    forward_coverage: float
    reverse_coverage: float
    usable_points: int
    reverse_error: float = float("inf")
    tangent_error: float = float("inf")

    @property
    def score(self) -> float:
        if self.usable_points <= 0:
            return 0.0
        symmetric_error = self.forward_error + (self.reverse_error if math.isfinite(self.reverse_error) else self.forward_error)
        tangent_score = 0.5 if not math.isfinite(self.tangent_error) else max(0.0, 1.0 - self.tangent_error)
        return (
            0.40 * self.forward_coverage
            + 0.30 * self.reverse_coverage
            + 0.20 * math.exp(-0.5 * symmetric_error)
            + 0.10 * tangent_score
        )


@dataclass(frozen=True)
class ReferenceGeometry:
    distance: np.ndarray
    points: np.ndarray
    tangents: np.ndarray


_REFERENCE_CACHE: "OrderedDict[tuple[object, ...], ReferenceGeometry]" = OrderedDict()
_REFERENCE_CACHE_LIMIT = 8


def _distance_field(mask: np.ndarray) -> np.ndarray:
    binary = np.where(np.asarray(mask) > 0, 0, 255).astype(np.uint8)
    return cv2.distanceTransform(binary, cv2.DIST_L2, 3)


def _local_tangents(mask: np.ndarray, points: np.ndarray, *, radius: int = 2) -> np.ndarray:
    binary = np.asarray(mask) > 0
    height, width = binary.shape
    tangents = np.full((len(points), 2), np.nan, dtype=np.float64)
    for index, (x_value, y_value) in enumerate(points):
        x, y = int(round(x_value)), int(round(y_value))
        x1, x2 = max(0, x - radius), min(width, x + radius + 1)
        y1, y2 = max(0, y - radius), min(height, y + radius + 1)
        local_y, local_x = np.nonzero(binary[y1:y2, x1:x2])
        if local_x.size < 2:
            continue
        samples = np.column_stack((local_x + x1, local_y + y1)).astype(np.float64)
        samples -= np.mean(samples, axis=0)
        covariance = samples.T @ samples
        values, vectors = np.linalg.eigh(covariance)
        direction = vectors[:, int(np.argmax(values))]
        norm = float(np.linalg.norm(direction))
        if norm > 1e-9:
            tangents[index] = direction / norm
    return tangents


def _reference_geometry(
    reference_boundary: np.ndarray,
    *,
    include_tangents: bool = True,
) -> ReferenceGeometry:
    reference = np.asarray(reference_boundary) > 0
    pointer = int(reference.__array_interface__["data"][0])
    key = (
        pointer,
        reference.shape,
        reference.strides,
        int(np.count_nonzero(reference)),
        bool(include_tangents),
    )
    cached = _REFERENCE_CACHE.get(key)
    if cached is not None:
        _REFERENCE_CACHE.move_to_end(key)
        return cached
    points = np.column_stack(np.nonzero(reference))[:, ::-1].astype(np.float64)
    geometry = ReferenceGeometry(
        distance=_distance_field(reference),
        points=points,
        tangents=(
            _local_tangents(reference, points)
            if include_tangents
            else np.empty((0, 2), dtype=np.float64)
        ),
    )
    _REFERENCE_CACHE[key] = geometry
    _REFERENCE_CACHE.move_to_end(key)
    while len(_REFERENCE_CACHE) > _REFERENCE_CACHE_LIMIT:
        _REFERENCE_CACHE.popitem(last=False)
    return geometry


def _huber(values: np.ndarray, delta: float) -> np.ndarray:
    absolute = np.abs(values)
    return np.where(
        absolute <= delta,
        0.5 * values * values,
        delta * (absolute - 0.5 * delta),
    )


def _robust_error(
    distances: np.ndarray,
    *,
    sigma: float,
    huber_delta: float,
    trim_fraction: float,
) -> float:
    scaled = np.asarray(distances, dtype=np.float64) / max(float(sigma), 1e-6)
    if scaled.size == 0:
        return float("inf")
    keep = max(1, int(math.ceil(scaled.size * (1.0 - float(trim_fraction)))))
    retained = np.partition(scaled, keep - 1)[:keep]
    return float(np.mean(_huber(retained, float(huber_delta))))


def _tangent_error(
    wall: np.ndarray,
    points: np.ndarray,
    projected: np.ndarray,
    transform: SimilarityTransform2D,
    geometry: ReferenceGeometry,
    *,
    max_samples: int = 1024,
) -> float:
    if points.size == 0 or geometry.points.size == 0:
        return float("inf")
    step = max(1, int(math.ceil(len(points) / max_samples)))
    source_points = points[::step]
    target_points = projected[::step].astype(np.float64)
    source_tangents = _local_tangents(wall, source_points)
    source_tips = source_points + source_tangents
    mapped_origins = transform_points(source_points, transform)
    mapped_tips = transform_points(source_tips, transform)
    mapped_tangents = mapped_tips - mapped_origins
    errors: list[float] = []
    for target, tangent in zip(target_points, mapped_tangents):
        if not np.isfinite(tangent).all():
            continue
        distances = np.sum((geometry.points - target) ** 2, axis=1)
        nearest = int(np.argmin(distances))
        reference_tangent = geometry.tangents[nearest]
        if not np.isfinite(reference_tangent).all():
            continue
        tangent_norm = float(np.linalg.norm(tangent))
        if tangent_norm <= 1e-9:
            continue
        cosine = float(np.clip(abs(np.dot(tangent / tangent_norm, reference_tangent)), 0.0, 1.0))
        errors.append(math.acos(cosine) / (math.pi / 2.0))
    return float(np.mean(errors)) if errors else float("inf")


def transform_points(points: np.ndarray, transform: SimilarityTransform2D) -> np.ndarray:
    values = np.asarray(points, dtype=np.float64)
    if values.ndim != 2 or values.shape[1] != 2:
        raise ValueError("points must have shape (n, 2)")
    if transform.reflect_horizontal:
        values = values.copy()
        values[:, 0] *= -1.0
    radians = math.radians(transform.angle_degrees)
    c, s = math.cos(radians), math.sin(radians)
    matrix = np.array([[c, s], [-s, c]], dtype=np.float64)
    return values @ matrix.T * float(transform.scale) + np.asarray(transform.translation)


def _project_observed(mask: np.ndarray, transform: SimilarityTransform2D, output_shape: tuple[int, int]) -> np.ndarray:
    binary = np.where(np.asarray(mask) > 0, 255, 0).astype(np.uint8)
    contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    projected = np.zeros(output_shape, dtype=np.uint8)
    for contour in contours:
        points = contour.reshape(-1, 2)
        if points.shape[0] < 3:
            continue
        mapped = np.rint(transform_points(points, transform)).astype(np.int32)
        cv2.fillPoly(projected, [mapped.reshape(-1, 1, 2)], 255)
    return projected


def score_shape(
    *,
    wall_mask: np.ndarray,
    observed_mask: np.ndarray,
    reference_boundary: np.ndarray,
    transform: SimilarityTransform2D,
    sigma: float = 3.0,
    threshold: float = 5.0,
    huber_delta: float = 1.5,
    trim_fraction: float = 0.1,
    include_tangent: bool = True,
    include_reverse: bool = True,
) -> ShapeScore:
    wall = np.asarray(wall_mask) > 0
    observed = np.asarray(observed_mask) > 0
    reference = np.asarray(reference_boundary) > 0
    if wall.ndim != 2 or observed.shape != wall.shape or reference.ndim != 2:
        raise ValueError("shape masks must be 2-D and compatible")
    if not 0 <= trim_fraction < 0.5 or huber_delta <= 0:
        raise ValueError("robust score parameters are invalid")
    points = np.column_stack(np.nonzero(wall & observed))[:, ::-1].astype(np.float64)
    if points.size == 0:
        return ShapeScore(float("inf"), 0.0, 0.0, 0, float("inf"), float("inf"))
    projected = np.rint(transform_points(points, transform)).astype(int)
    inside = (
        (projected[:, 0] >= 0) & (projected[:, 0] < reference.shape[1])
        & (projected[:, 1] >= 0) & (projected[:, 1] < reference.shape[0])
    )
    projected = projected[inside]
    if projected.size == 0:
        return ShapeScore(float("inf"), 0.0, 0.0, 0, float("inf"), float("inf"))
    source_points = points[inside]
    geometry = _reference_geometry(reference, include_tangents=include_tangent)
    distances = geometry.distance[projected[:, 1], projected[:, 0]]
    usable = int(distances.size)
    forward = float(np.mean(distances <= float(threshold)))
    if include_reverse:
        projected_wall = np.zeros(reference.shape, dtype=np.uint8)
        projected_wall[projected[:, 1], projected[:, 0]] = 255
        projected_observed = _project_observed(observed, transform, reference.shape) > 0
        reverse_points = np.column_stack(np.nonzero(reference & projected_observed))
        if reverse_points.size:
            reverse_distance = _distance_field(projected_wall)
            reverse_distances = reverse_distance[reverse_points[:, 0], reverse_points[:, 1]]
            reverse = float(np.mean(reverse_distances <= float(threshold)))
            reverse_error = _robust_error(
                reverse_distances,
                sigma=sigma,
                huber_delta=huber_delta,
                trim_fraction=trim_fraction,
            )
        else:
            reverse = 0.0
            reverse_error = float("inf")
    else:
        reverse = 0.0
        reverse_error = float("inf")
    tangent_error = (
        _tangent_error(
            wall,
            source_points,
            projected,
            transform,
            geometry,
        )
        if include_tangent
        else float("inf")
    )
    return ShapeScore(
        _robust_error(
            distances,
            sigma=sigma,
            huber_delta=huber_delta,
            trim_fraction=trim_fraction,
        ),
        forward,
        reverse,
        usable,
        reverse_error,
        tangent_error,
    )


__all__ = ["ShapeScore", "score_shape", "transform_points"]
