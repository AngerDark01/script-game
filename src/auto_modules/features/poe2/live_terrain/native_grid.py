"""Validated conversion from the temporary producer's native NPZ export."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np

from .contracts import CaptureMetadata, TerrainCaptureError, TerrainSnapshot
from .logging_utils import get_terrain_logger

REQUIRED_KEYS = frozenset(
    {"raw_cells", "cell_state", "known_mask", "wall_layer", "explored_map", "metadata_json"}
)


def _scalar_text(value: Any) -> str:
    array = np.asarray(value)
    if array.ndim == 0:
        value = array.item()
    if isinstance(value, bytes):
        return value.decode("utf-8")
    if not isinstance(value, str):
        raise TerrainCaptureError("metadata_json must be a scalar string")
    return value


def _metadata_from_json(value: Any) -> CaptureMetadata:
    try:
        payload = json.loads(_scalar_text(value))
    except (UnicodeDecodeError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise TerrainCaptureError("metadata_json is not valid JSON") from exc
    if not isinstance(payload, dict):
        raise TerrainCaptureError("metadata_json must contain an object")
    try:
        return CaptureMetadata(
            area_id=str(payload["area_id"]),
            area_hash=str(payload.get("area_hash", "")),
            instance_id=str(payload["instance_id"]),
            width=int(payload["width"]),
            height=int(payload["height"]),
            captured_at=str(payload["captured_at"]),
            raw_sha256=str(payload.get("raw_sha256", "")),
            tool=str(payload.get("tool", "manual-live-terrain-capture")),
            extra=payload,
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise TerrainCaptureError("metadata_json is missing valid terrain identity") from exc


def load_native_grid(path: str | Path) -> TerrainSnapshot:
    path = Path(path)
    logger = get_terrain_logger()
    logger.info("step=convert.start path=%s", path)
    if not path.is_file():
        logger.error("step=convert.reject reason=missing path=%s", path)
        raise TerrainCaptureError(f"native grid does not exist: {path}")
    try:
        with np.load(path, allow_pickle=False) as data:
            missing = REQUIRED_KEYS.difference(data.files)
            if missing:
                raise TerrainCaptureError(f"native grid is missing keys: {sorted(missing)}")
            metadata = _metadata_from_json(data["metadata_json"])
            snapshot = TerrainSnapshot(
                metadata=metadata,
                raw_cells=np.asarray(data["raw_cells"], dtype=np.uint8),
                cell_state=np.asarray(data["cell_state"], dtype=np.int8),
                known_mask=np.asarray(data["known_mask"], dtype=np.uint8),
                wall_layer=np.asarray(data["wall_layer"], dtype=np.uint8),
                explored_map=np.asarray(data["explored_map"], dtype=np.uint8),
            )
            logger.info(
                "step=convert.success shape=%sx%s dtype=raw:%s state:%s",
                metadata.height,
                metadata.width,
                snapshot.raw_cells.dtype,
                snapshot.cell_state.dtype,
            )
            return snapshot
    except TerrainCaptureError:
        logger.exception("step=convert.reject path=%s", path)
        raise
    except (OSError, ValueError, TypeError, UnicodeError) as exc:
        logger.exception("step=convert.reject reason=invalid_data path=%s", path)
        raise TerrainCaptureError(f"could not load native grid: {path}") from exc
