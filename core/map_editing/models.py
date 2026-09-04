from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass
class WallOverrideDocument:
    """Manual add/erase masks stored independently from the generated map."""

    add_mask: np.ndarray
    erase_mask: np.ndarray

    @classmethod
    def empty(cls, shape: tuple[int, int]) -> "WallOverrideDocument":
        if len(shape) != 2 or min(shape) <= 0:
            raise ValueError("wall override shape must be a positive two-dimensional shape")
        return cls(
            add_mask=np.zeros(shape, dtype=np.uint8),
            erase_mask=np.zeros(shape, dtype=np.uint8),
        )

    def validate_for(self, shape: tuple[int, int]) -> None:
        if self.add_mask.ndim != 2 or self.erase_mask.ndim != 2:
            raise ValueError("wall override masks must be two-dimensional")
        if self.add_mask.shape != shape or self.erase_mask.shape != shape:
            raise ValueError(f"wall override shape must match base wall shape {shape}")

    @property
    def has_changes(self) -> bool:
        return bool(np.any(self.add_mask) or np.any(self.erase_mask))
