from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass
class PortalFeatureTemplate:
    name: str
    mask: np.ndarray


@dataclass
class PortalFeatureHit:
    score: float
    mask_score: float
    density_score: float
    scale: float
    top_left: tuple[int, int]
    size: tuple[int, int]
    template_name: str
    blue_pixels: int
    template_pixels: int

    @property
    def center(self) -> tuple[int, int]:
        return (
            int(self.top_left[0] + self.size[0] / 2),
            int(self.top_left[1] + self.size[1] / 2),
        )
