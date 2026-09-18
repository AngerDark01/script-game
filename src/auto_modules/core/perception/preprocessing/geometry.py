"""Image geometry operations that preserve source-frame coordinate recovery."""

from __future__ import annotations

from typing import Any

import cv2

from .models import ImageArtifact, ImageGeometry, Matrix3x3


def crop(
    artifact: ImageArtifact,
    *,
    left: int,
    top: int,
    width: int,
    height: int,
) -> ImageArtifact:
    """Crop an artifact and compose its output-to-source translation."""
    _require_artifact(artifact)
    _require_positive_int("width", width)
    _require_positive_int("height", height)
    if left < 0 or top < 0 or left + width > artifact.geometry.output_width or top + height > artifact.geometry.output_height:
        raise ValueError("crop must stay within artifact bounds")
    image = artifact.image[top : top + height, left : left + width].copy()
    return _with_geometry(
        artifact,
        image,
        output_width=width,
        output_height=height,
        output_to_previous=(
            (1.0, 0.0, float(left)),
            (0.0, 1.0, float(top)),
            (0.0, 0.0, 1.0),
        ),
    )


def resize(
    artifact: ImageArtifact,
    *,
    width: int,
    height: int,
    interpolation: int = cv2.INTER_LINEAR,
) -> ImageArtifact:
    """Resize an artifact and compose the inverse output-to-prior scaling."""
    _require_artifact(artifact)
    _require_positive_int("width", width)
    _require_positive_int("height", height)
    image = cv2.resize(artifact.image, (width, height), interpolation=interpolation)
    return _with_geometry(
        artifact,
        image,
        output_width=width,
        output_height=height,
        output_to_previous=(
            (artifact.geometry.output_width / float(width), 0.0, 0.0),
            (0.0, artifact.geometry.output_height / float(height), 0.0),
            (0.0, 0.0, 1.0),
        ),
    )


def pad(
    artifact: ImageArtifact,
    *,
    left: int,
    top: int,
    right: int,
    bottom: int,
    border_type: int = cv2.BORDER_CONSTANT,
    value: Any = 0,
) -> ImageArtifact:
    """Pad an artifact and compose the inverse output-to-prior translation."""
    _require_artifact(artifact)
    for name, amount in (("left", left), ("top", top), ("right", right), ("bottom", bottom)):
        if not isinstance(amount, int) or isinstance(amount, bool) or amount < 0:
            raise ValueError(f"{name} must be a non-negative integer")
    image = cv2.copyMakeBorder(artifact.image, top, bottom, left, right, border_type, value=value)
    return _with_geometry(
        artifact,
        image,
        output_width=artifact.geometry.output_width + left + right,
        output_height=artifact.geometry.output_height + top + bottom,
        output_to_previous=(
            (1.0, 0.0, -float(left)),
            (0.0, 1.0, -float(top)),
            (0.0, 0.0, 1.0),
        ),
    )


def _with_geometry(
    artifact: ImageArtifact,
    image,
    *,
    output_width: int,
    output_height: int,
    output_to_previous: Matrix3x3,
) -> ImageArtifact:
    geometry = artifact.geometry
    return ImageArtifact(
        image=image,
        frame=artifact.frame,
        geometry=ImageGeometry(
            source_width=geometry.source_width,
            source_height=geometry.source_height,
            output_width=output_width,
            output_height=output_height,
            coordinate_space=geometry.coordinate_space,
            output_to_source=_multiply(geometry.output_to_source, output_to_previous),
        ),
        metadata=dict(artifact.metadata),
    )


def _multiply(first: Matrix3x3, second: Matrix3x3) -> Matrix3x3:
    return tuple(
        tuple(sum(first[row][index] * second[index][column] for index in range(3)) for column in range(3))
        for row in range(3)
    )  # type: ignore[return-value]


def _require_artifact(artifact: ImageArtifact) -> None:
    if not isinstance(artifact, ImageArtifact):
        raise TypeError("artifact must be an ImageArtifact")


def _require_positive_int(name: str, value: int) -> None:
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise ValueError(f"{name} must be a positive integer")
