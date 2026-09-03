from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import numpy as np

from core.perception.models import CoordinateSpace

from .models import CoordinateAnchor, Point2D


@dataclass(frozen=True)
class AffineTransform:
    """Two-dimensional affine transform fitted from runtime anchor pairs."""

    a: float
    b: float
    c: float
    d: float
    e: float
    f: float

    def map_point(self, point: Point2D) -> Point2D:
        return Point2D(
            self.a * point.x + self.b * point.y + self.c,
            self.d * point.x + self.e * point.y + self.f,
        )


def fit_affine_transform(anchors: Iterable[CoordinateAnchor]) -> AffineTransform:
    """Fit an affine transform and reject insufficient or collinear anchors."""
    items = tuple(anchors)
    if len(items) < 3:
        raise ValueError("at least three anchors are required")

    matrix = []
    values = []
    for anchor in items:
        x, y = anchor.source.x, anchor.source.y
        matrix.extend(((x, y, 1.0, 0.0, 0.0, 0.0), (0.0, 0.0, 0.0, x, y, 1.0)))
        values.extend((anchor.target.x, anchor.target.y))
    coefficients, _, rank, _ = np.linalg.lstsq(
        np.asarray(matrix, dtype=float),
        np.asarray(values, dtype=float),
        rcond=None,
    )
    if int(rank) < 6:
        raise ValueError("anchor points must not be collinear")
    return AffineTransform(*(float(value) for value in coefficients))


class CoordinateMapper:
    """Store calibrated transforms between explicit coordinate spaces."""

    def __init__(self) -> None:
        self._transforms: dict[tuple[CoordinateSpace, CoordinateSpace], AffineTransform] = {}

    def register(
        self,
        source_space: CoordinateSpace,
        target_space: CoordinateSpace,
        transform: AffineTransform,
    ) -> None:
        self._transforms[(source_space, target_space)] = transform

    def map(
        self,
        point: Point2D,
        source_space: CoordinateSpace,
        target_space: CoordinateSpace,
    ) -> Point2D:
        if source_space == target_space:
            return point
        try:
            transform = self._transforms[(source_space, target_space)]
        except KeyError as exc:
            raise KeyError(
                f"no coordinate transform registered: {source_space.value} -> {target_space.value}"
            ) from exc
        return transform.map_point(point)
