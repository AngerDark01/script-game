"""Typed visual evidence supplied to legacy-compatible map stitching."""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any

import numpy as np

from core.perception.models import CoordinateSpace, FrameContext


@dataclass(frozen=True)
class MapFrameEvidence:
    """One minimap/map-view frame and the feature layers derived from it."""

    image: np.ndarray
    match_mask: np.ndarray
    save_mask: np.ndarray
    fog_mask: np.ndarray
    player_position: tuple[float, float] | None = None
    raw_gray: np.ndarray | None = None
    coordinate_space: CoordinateSpace = CoordinateSpace.MINIMAP
    source_frame: FrameContext | None = None
    metadata: dict[str, Any] | None = None

    def __post_init__(self) -> None:
        image_height, image_width = _image_shape(self.image, "image")
        for name, mask in (
            ("match_mask", self.match_mask),
            ("save_mask", self.save_mask),
            ("fog_mask", self.fog_mask),
        ):
            if _mask_shape(mask, name) != (image_height, image_width):
                raise ValueError(f"{name} dimensions must match image dimensions")
        if self.raw_gray is not None and _mask_shape(self.raw_gray, "raw_gray") != (image_height, image_width):
            raise ValueError("raw_gray dimensions must match image dimensions")
        if not isinstance(self.coordinate_space, CoordinateSpace):
            raise TypeError("coordinate_space must be a CoordinateSpace")
        if self.source_frame is not None and not isinstance(self.source_frame, FrameContext):
            raise TypeError("source_frame must be a FrameContext or None")
        if self.player_position is not None:
            if len(self.player_position) != 2 or any(not math.isfinite(float(value)) for value in self.player_position):
                raise ValueError("player_position must contain two finite coordinates")


def _image_shape(image: np.ndarray, name: str) -> tuple[int, int]:
    if not isinstance(image, np.ndarray) or image.ndim not in (2, 3) or image.size == 0:
        raise ValueError(f"{name} must be a non-empty 2D or 3D numpy array")
    return int(image.shape[0]), int(image.shape[1])


def _mask_shape(mask: np.ndarray, name: str) -> tuple[int, int]:
    if not isinstance(mask, np.ndarray) or mask.ndim != 2 or mask.size == 0:
        raise ValueError(f"{name} must be a non-empty 2D numpy array")
    return int(mask.shape[0]), int(mask.shape[1])
