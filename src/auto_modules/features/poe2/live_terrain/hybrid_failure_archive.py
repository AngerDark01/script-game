"""Failure snapshots for PoE2 hybrid-localization diagnostics."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Mapping

import numpy as np

from .capture_samples import CaptureEvidence, CaptureSampleArchive
from .contracts import TerrainSnapshot
from .logging_utils import get_terrain_logger


def _jsonable(value: Any) -> Any:
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, Mapping):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    enum_value = getattr(value, "value", None)
    if isinstance(enum_value, (bool, int, float, str)):
        return enum_value
    return str(value)


class Poe2HybridFailureArchive:
    """Persist one complete visual/state package for a localization failure."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root).expanduser().resolve()
        self._samples = CaptureSampleArchive(self.root)
        self._logger = get_terrain_logger()

    def record(
        self,
        *,
        experiment: Any,
        state: Any,
        snapshot: TerrainSnapshot,
    ) -> Path:
        session = experiment.session
        evidence = getattr(session, "last_evidence", None)
        if not isinstance(evidence, CaptureEvidence):
            raise RuntimeError("failure snapshot requires the latest CaptureEvidence")
        if not isinstance(snapshot, TerrainSnapshot):
            raise TypeError("snapshot must be a TerrainSnapshot")

        record = self._samples.save(evidence, terrain=snapshot)
        frame = getattr(session, "last_frame", None)
        controller = getattr(experiment, "controller", None)
        confirmed = getattr(controller, "last_confirmed", None)
        transform = getattr(confirmed, "transform", None)
        payload = {
            "tool": "poe2-hybrid-localization-failure",
            "mode": _jsonable(getattr(state, "mode", "unknown")),
            "source": str(getattr(state, "source", "failed")),
            "confidence": float(getattr(state, "confidence", 0.0)),
            "position": _jsonable(getattr(state, "position", None)),
            "latest_confirmed_position": _jsonable(
                getattr(state, "latest_confirmed_position", None)
            ),
            "trajectory": _jsonable(getattr(state, "trajectory", ())),
            "reason": str(getattr(state, "reason", "") or ""),
            "recovery_revision": int(getattr(state, "recovery_revision", 0)),
            "memory_read_count": int(getattr(state, "memory_read_count", 0)),
            "frame_elapsed_ms": float(getattr(state, "frame_elapsed_ms", 0.0)),
            "diagnostics": _jsonable(getattr(state, "diagnostics", {}) or {}),
            "frame": {
                "frame_id": int(getattr(frame, "frame_id", 0)),
                "captured_at_ms": int(getattr(frame, "captured_at_ms", 0)),
                "local_player": _jsonable(getattr(frame, "local_player", None)),
            },
            "last_confirmed_transform": None
            if transform is None
            else {
                "angle_deg": float(transform.angle_degrees),
                "flip_horizontal": bool(transform.flip_horizontal),
                "scale": float(transform.scale),
                "translation": _jsonable(transform.translation),
            },
            "sample_manifest": "sample.json",
        }
        temporary = record.path / "localization_failure.json.tmp"
        destination = record.path / "localization_failure.json"
        temporary.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        os.replace(temporary, destination)
        self._logger.warning(
            "step=product_localization.failure_snapshot_saved path=%s reason=%s revision=%s",
            record.path,
            payload["reason"],
            payload["recovery_revision"],
        )
        return record.path


__all__ = ["Poe2HybridFailureArchive"]
