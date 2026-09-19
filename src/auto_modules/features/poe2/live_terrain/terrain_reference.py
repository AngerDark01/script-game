"""PoE2 terrain data prepared for localization, independent of UI rendering."""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Mapping

import numpy as np

from .contracts import TerrainSnapshot


def _readonly(value, *, dtype=None) -> np.ndarray:
    array = np.array(value, dtype=dtype, copy=True, order="C")
    array.setflags(write=False)
    return array


@dataclass(frozen=True)
class TerrainReference:
    """Immutable map layers used by a localization matcher."""

    walkable_mask: np.ndarray
    wall_layer: np.ndarray
    explored_map: np.ndarray
    width: int
    height: int
    metadata: Mapping[str, Any] = MappingProxyType({})

    def __post_init__(self) -> None:
        shape = (int(self.height), int(self.width))
        if self.width <= 0 or self.height <= 0:
            raise ValueError("terrain reference dimensions must be positive")
        for name, dtype in (
            ("walkable_mask", np.bool_),
            ("wall_layer", np.uint8),
            ("explored_map", np.uint8),
        ):
            value = _readonly(getattr(self, name), dtype=dtype)
            if value.shape != shape:
                raise ValueError(f"{name} must have shape {shape}, got {value.shape}")
            object.__setattr__(self, name, value)
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))

    @property
    def shape(self) -> tuple[int, int]:
        return self.height, self.width


def build_reference(snapshot: TerrainSnapshot) -> TerrainReference:
    """Convert a native terrain snapshot into matching layers.

    Unknown cells are excluded from walkable geometry.  The wall layer uses
    the generic matcher convention (zero for walkable, 255 for blocked or
    unknown) and is deliberately derived from native arrays rather than the
    display pixmap.
    """
    if not isinstance(snapshot, TerrainSnapshot):
        raise TypeError("snapshot must be a TerrainSnapshot")
    known = np.asarray(snapshot.known_mask) > 0
    walkable = (np.asarray(snapshot.cell_state) == 1) & known
    wall_layer = np.where(walkable, 0, 255).astype(np.uint8)
    explored = np.where(known, 255, 0).astype(np.uint8)
    metadata = {
        "instance_id": snapshot.metadata.instance_id,
        "area_id": snapshot.metadata.area_id,
        "area_hash": snapshot.metadata.area_hash,
        "captured_at": snapshot.metadata.captured_at,
    }
    return TerrainReference(
        walkable_mask=walkable,
        wall_layer=wall_layer,
        explored_map=explored,
        width=snapshot.metadata.width,
        height=snapshot.metadata.height,
        metadata=metadata,
    )


__all__ = ["TerrainReference", "build_reference"]
