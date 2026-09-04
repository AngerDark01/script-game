"""Geometry-aware image artifacts for reusable visual preprocessing."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from core.perception.models import BoundingBox, CoordinateSpace, FrameContext


Matrix3x3 = tuple[
    tuple[float, float, float],
    tuple[float, float, float],
    tuple[float, float, float],
]


@dataclass(frozen=True)
class ImageGeometry:
    """Maps an artifact's output pixels back to its source frame pixels."""

    source_width: int
    source_height: int
    output_width: int
    output_height: int
    coordinate_space: CoordinateSpace
    output_to_source: Matrix3x3

    def __post_init__(self) -> None:
        for name, value in (
            ("source_width", self.source_width),
            ("source_height", self.source_height),
            ("output_width", self.output_width),
            ("output_height", self.output_height),
        ):
            if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
                raise ValueError(f"{name} must be a positive integer")
        if not isinstance(self.coordinate_space, CoordinateSpace):
            raise TypeError("coordinate_space must be a CoordinateSpace")
        if len(self.output_to_source) != 3 or any(len(row) != 3 for row in self.output_to_source):
            raise ValueError("output_to_source must be a 3x3 matrix")

    @classmethod
    def identity(
        cls,
        *,
        width: int,
        height: int,
        coordinate_space: CoordinateSpace,
    ) -> ImageGeometry:
        """Create geometry for an artifact that has not changed image coordinates."""
        return cls(
            source_width=width,
            source_height=height,
            output_width=width,
            output_height=height,
            coordinate_space=coordinate_space,
            output_to_source=(
                (1.0, 0.0, 0.0),
                (0.0, 1.0, 0.0),
                (0.0, 0.0, 1.0),
            ),
        )

    def map_point_to_source(self, point: tuple[float, float]) -> tuple[float, float]:
        """Map one artifact pixel coordinate into the source-frame coordinate system."""
        if len(point) != 2:
            raise ValueError("point must contain exactly two coordinates")
        x, y = float(point[0]), float(point[1])
        matrix = self.output_to_source
        source_x = matrix[0][0] * x + matrix[0][1] * y + matrix[0][2]
        source_y = matrix[1][0] * x + matrix[1][1] * y + matrix[1][2]
        homogeneous = matrix[2][0] * x + matrix[2][1] * y + matrix[2][2]
        if abs(homogeneous) < 1e-12:
            raise ValueError("output_to_source maps point to an invalid homogeneous coordinate")
        return source_x / homogeneous, source_y / homogeneous

    def map_box_to_source(self, box: BoundingBox) -> BoundingBox:
        """Map an axis-aligned artifact box to the source-frame enclosing box."""
        if not isinstance(box, BoundingBox):
            raise TypeError("box must be a BoundingBox")
        corners = (
            self.map_point_to_source((box.left, box.top)),
            self.map_point_to_source((box.left + box.width, box.top)),
            self.map_point_to_source((box.left, box.top + box.height)),
            self.map_point_to_source((box.left + box.width, box.top + box.height)),
        )
        xs, ys = zip(*corners)
        left, top = min(xs), min(ys)
        return BoundingBox(left, top, max(xs) - left, max(ys) - top)


@dataclass(frozen=True)
class ImageArtifact:
    """Processed pixels plus their immutable source-frame and geometry context."""

    image: Any
    frame: FrameContext
    geometry: ImageGeometry
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.frame, FrameContext):
            raise TypeError("frame must be a FrameContext")
        if not isinstance(self.geometry, ImageGeometry):
            raise TypeError("geometry must be an ImageGeometry")
        shape = getattr(self.image, "shape", None)
        if shape is None or len(shape) < 2:
            raise ValueError("image must expose at least height and width through shape")
        height, width = int(shape[0]), int(shape[1])
        if (width, height) != (self.geometry.output_width, self.geometry.output_height):
            raise ValueError("image dimensions must match geometry output dimensions")
        if self.frame.width is not None and self.frame.width != self.geometry.source_width:
            raise ValueError("frame width must match geometry source width")
        if self.frame.height is not None and self.frame.height != self.geometry.source_height:
            raise ValueError("frame height must match geometry source height")
        if self.frame.coordinate_space != self.geometry.coordinate_space:
            raise ValueError("frame and geometry coordinate spaces must match")
