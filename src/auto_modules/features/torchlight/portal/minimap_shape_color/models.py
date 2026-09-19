from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np


@dataclass
class PortalShapeColorParams:
    threshold: float = 0.70
    hue_min: int = 82
    hue_max: int = 136
    sat_min: int = 55
    val_min: int = 95
    outer_sat_max: int = 115
    outer_val_min: int = 105
    min_blue_pixels: int = 18
    max_blue_pixels: int = 520
    min_outer_pixels: int = 14
    min_blue_score: float = 0.28
    min_outer_score: float = 0.18
    min_shape_score: float = 0.30
    signature_min_outer_score: float = 0.45
    signature_min_edge_score: float = 0.40
    signature_min_color_score: float = 0.82
    signature_score_scale: float = 1.30


@dataclass
class PortalShapeColorHit:
    score: float
    blue_score: float
    outer_score: float
    shape_score: float
    edge_score: float
    color_score: float
    signature_score: float
    response_score: float
    scale: float
    top_left: tuple[int, int]
    size: tuple[int, int]
    template_name: str
    blue_pixels: int
    outer_pixels: int
    template_blue_pixels: int
    template_outer_pixels: int
    accepted: bool
    reject_reasons: list[str] = field(default_factory=list)

    @property
    def center(self) -> tuple[int, int]:
        return (
            int(self.top_left[0] + self.size[0] / 2),
            int(self.top_left[1] + self.size[1] / 2),
        )


@dataclass
class PortalShapeColorDebug:
    frame_blue_mask: np.ndarray
    frame_outer_mask: np.ndarray
    frame_shape_mask: np.ndarray


@dataclass
class PreparedShapeColorTemplate:
    name: str
    scale: float
    image: np.ndarray
    blue_mask: np.ndarray
    outer_mask: np.ndarray
    shape_mask: np.ndarray
    edge_mask: np.ndarray
