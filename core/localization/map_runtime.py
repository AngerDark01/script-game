"""Reusable cached map view built on the existing navigation map package."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np


@dataclass(frozen=True)
class MapRuntime:
    map_id: str
    map_version: str
    wall_layer: np.ndarray
    distance_field: np.ndarray
    tile_size: int = 256

    @classmethod
    def from_wall_layer(cls, wall_layer, *, map_id="map", map_version="active", tile_size=256):
        walls = np.asarray(wall_layer)
        if walls.ndim != 2 or walls.size == 0:
            raise ValueError("wall_layer must be a non-empty 2D array")
        walls = (walls > 0).astype(np.uint8)
        # Distance to the nearest wall; matching code can score local patches
        # without rebuilding this field for every frame.
        free = (walls == 0).astype(np.uint8)
        distance = cv2.distanceTransform(free, cv2.DIST_L2, 3)
        return cls(str(map_id), str(map_version), walls, distance, int(tile_size))

    @classmethod
    def from_npz(cls, path, *, map_id=None, map_version="active", tile_size=256):
        source = Path(path)
        with np.load(source) as data:
            if "wall_layer" not in data:
                raise KeyError("map package must contain wall_layer")
            wall_layer = data["wall_layer"]
        return cls.from_wall_layer(
            wall_layer,
            map_id=map_id or source.stem,
            map_version=map_version,
            tile_size=tile_size,
        )

    @property
    def shape(self):
        return self.wall_layer.shape

    def tile(self, x, y, *, radius=0):
        """Return a clipped wall/distance tile around map pixel (x, y)."""
        cx, cy = int(x), int(y)
        half = self.tile_size // 2 + int(radius)
        x1, y1 = max(0, cx - half), max(0, cy - half)
        x2, y2 = min(self.shape[1], cx + half), min(self.shape[0], cy + half)
        return self.wall_layer[y1:y2, x1:x2], self.distance_field[y1:y2, x1:x2], (x1, y1)
