from __future__ import annotations

import numpy as np

from .models import WallOverrideDocument


def compose_effective_wall_layer(base_wall: np.ndarray, overrides: WallOverrideDocument) -> np.ndarray:
    """Apply manual erasures and additions without mutating the generated wall layer."""
    if base_wall.ndim != 2:
        raise ValueError("base wall layer must be two-dimensional")
    overrides.validate_for(tuple(base_wall.shape))
    effective = base_wall.copy()
    effective[overrides.erase_mask > 0] = 0
    effective[overrides.add_mask > 0] = 255
    return effective
