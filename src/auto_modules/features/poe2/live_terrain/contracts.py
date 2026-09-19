"""Stable contracts for the PoE2 live-terrain feature."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from types import MappingProxyType
from typing import Any, Mapping

import numpy as np


class TerrainCaptureError(RuntimeError):
    """Raised when a live terrain capture cannot be trusted."""


class TerrainSessionState(str, Enum):
    NEW = "new"
    INITIALIZED = "initialized"
    READY_TO_CAPTURE = "ready_to_capture"
    CAPTURED = "captured"
    INVALIDATED = "invalidated"
    ERROR = "error"


def readonly_array(value: Any, *, dtype: np.dtype | type | None = None) -> np.ndarray:
    array = np.array(value, dtype=dtype, copy=True, order="C")
    array.setflags(write=False)
    return array


@dataclass(frozen=True)
class CaptureMetadata:
    area_id: str
    area_hash: str
    instance_id: str
    width: int
    height: int
    captured_at: str
    raw_sha256: str = ""
    tool: str = "manual-live-terrain-capture"
    extra: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.width <= 0 or self.height <= 0:
            raise ValueError("terrain dimensions must be positive")
        if not self.area_id or not self.instance_id:
            raise ValueError("terrain metadata requires area_id and instance_id")
        try:
            datetime.fromisoformat(self.captured_at.replace("Z", "+00:00"))
        except (TypeError, ValueError) as exc:
            raise ValueError("captured_at must be an ISO timestamp") from exc
        object.__setattr__(self, "extra", MappingProxyType(dict(self.extra)))


@dataclass(frozen=True)
class TerrainSnapshot:
    metadata: CaptureMetadata
    raw_cells: np.ndarray
    cell_state: np.ndarray
    known_mask: np.ndarray
    wall_layer: np.ndarray
    explored_map: np.ndarray

    def __post_init__(self) -> None:
        arrays = {
            "raw_cells": self.raw_cells,
            "cell_state": self.cell_state,
            "known_mask": self.known_mask,
            "wall_layer": self.wall_layer,
            "explored_map": self.explored_map,
        }
        shape = (self.metadata.height, self.metadata.width)
        for name, value in arrays.items():
            array = readonly_array(value)
            if array.ndim != 2 or array.shape != shape:
                raise ValueError(f"{name} must have shape {shape}, got {array.shape}")
            object.__setattr__(self, name, array)
        if self.raw_cells.dtype != np.uint8:
            raise ValueError("raw_cells must use uint8")
        if self.cell_state.dtype != np.int8:
            raise ValueError("cell_state must use int8")
        for name in ("known_mask", "wall_layer", "explored_map"):
            if getattr(self, name).dtype != np.uint8:
                raise ValueError(f"{name} must use uint8")
        if not np.isin(self.cell_state, (-1, 0, 1)).all():
            raise ValueError("cell_state contains unsupported values")
