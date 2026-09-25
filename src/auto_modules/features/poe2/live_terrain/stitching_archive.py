"""Explicit archive for PoE2 local-map stitching experiments."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import shutil
from typing import Any

import cv2
import numpy as np

from .capture_samples import CaptureEvidence, terrain_preview
from .contracts import TerrainSnapshot
from .stitching_session import Poe2StitchingSnapshot


STITCHING_SCHEMA_VERSION = 1


class Poe2StitchingArchive:
    """Atomically save one explicitly requested stitching experiment."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root).expanduser().resolve()

    def save(
        self,
        snapshot: Poe2StitchingSnapshot,
        evidence: CaptureEvidence,
        *,
        terrain: TerrainSnapshot | None = None,
    ) -> Path:
        if not isinstance(snapshot, Poe2StitchingSnapshot):
            raise TypeError("snapshot must be Poe2StitchingSnapshot")
        if not isinstance(evidence, CaptureEvidence):
            raise TypeError("evidence must be CaptureEvidence")
        if snapshot.map_image is None or not snapshot.trajectory:
            raise RuntimeError("no accepted stitching frame is available")

        self.root.mkdir(parents=True, exist_ok=True)
        destination = self._destination(evidence)
        temporary = self._temporary_directory()
        try:
            images: dict[str, dict[str, Any]] = {}
            layers = {
                "stitched_map": snapshot.map_image,
                "stitched_map_overlay": self._overlay(snapshot),
                "raw": evidence.raw,
                "processed": evidence.processed,
                "feature": evidence.feature,
                "wall_mask": evidence.wall_mask if evidence.wall_mask is not None else evidence.feature,
                "fog_mask": (
                    evidence.fog_mask
                    if evidence.fog_mask is not None
                    else np.zeros(evidence.feature.shape[:2], dtype=np.uint8)
                ),
            }
            for name, image in layers.items():
                images[name] = self._write_png(temporary / f"{name}.png", image)
            if terrain is not None:
                images["terrain"] = self._write_png(
                    temporary / "terrain.png",
                    terrain_preview(terrain, evidence.monitor_config),
                )
                terrain_payload = {
                    "status": "available",
                    "area_id": terrain.metadata.area_id,
                    "area_hash": terrain.metadata.area_hash,
                    "instance_id": terrain.metadata.instance_id,
                    "width": terrain.metadata.width,
                    "height": terrain.metadata.height,
                    "captured_at": terrain.metadata.captured_at,
                }
            else:
                terrain_payload = {
                    "status": "missing",
                    "reason": "no current terrain snapshot",
                }

            payload = {
                "schema_version": STITCHING_SCHEMA_VERSION,
                "saved_at": datetime.now(timezone.utc).isoformat(),
                "captured_at": evidence.captured_at,
                "state": snapshot.state,
                "map_origin": list(snapshot.map_origin),
                "current_position": (
                    list(snapshot.current_position)
                    if snapshot.current_position is not None
                    else None
                ),
                "trajectory": [list(point) for point in snapshot.trajectory],
                "statistics": dict(snapshot.statistics),
                "draw_scale": snapshot.draw_scale,
                "player_position": list(snapshot.player_position or ()),
                "capture_size": list(snapshot.capture_size or ()),
                "monitor_config": json.loads(
                    json.dumps(dict(evidence.monitor_config), ensure_ascii=False, default=str)
                ),
                "terrain": terrain_payload,
                "images": images,
            }
            (temporary / "session.json").write_text(
                json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            os.replace(temporary, destination)
        except Exception:
            shutil.rmtree(temporary, ignore_errors=True)
            raise
        return destination

    def _destination(self, evidence: CaptureEvidence) -> Path:
        try:
            captured = datetime.fromisoformat(evidence.captured_at.replace("Z", "+00:00"))
        except ValueError:
            captured = datetime.now(timezone.utc)
        profile = self._safe_name(evidence.monitor_config.get("profile_id", "profile"))
        stem = f"{captured.strftime('%Y%m%d-%H%M%S-%f')}-{profile}"
        destination = self.root / stem
        suffix = 1
        while destination.exists():
            destination = self.root / f"{stem}-{suffix}"
            suffix += 1
        return destination

    def _temporary_directory(self) -> Path:
        for _attempt in range(100):
            candidate = self.root / f".stitching-{secrets.token_hex(8)}"
            try:
                candidate.mkdir()
            except FileExistsError:
                continue
            return candidate
        raise FileExistsError("could not allocate a stitching archive directory")

    @staticmethod
    def _safe_name(value: Any) -> str:
        cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "-", str(value)).strip("-._")
        return cleaned or "profile"

    @staticmethod
    def _write_png(path: Path, value: Any) -> dict[str, Any]:
        image = np.asarray(value)
        if image.size == 0 or image.ndim not in (2, 3):
            raise ValueError(f"{path.name} must be a non-empty image")
        if image.dtype != np.uint8:
            image = np.clip(image, 0, 255).astype(np.uint8)
        ok, encoded = cv2.imencode(".png", image)
        if not ok:
            raise RuntimeError(f"could not encode {path.name}")
        data = encoded.tobytes()
        path.write_bytes(data)
        return {
            "file": path.name,
            "width": int(image.shape[1]),
            "height": int(image.shape[0]),
            "channels": int(image.shape[2]) if image.ndim == 3 else 1,
            "sha256": hashlib.sha256(data).hexdigest(),
        }

    @staticmethod
    def _overlay(snapshot: Poe2StitchingSnapshot) -> np.ndarray:
        image = np.asarray(snapshot.map_image)
        overlay = (
            cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
            if image.ndim == 2
            else np.array(image, copy=True)
        )
        origin_x, origin_y = snapshot.map_origin
        points = np.asarray(
            [(x - origin_x, y - origin_y) for x, y in snapshot.trajectory],
            dtype=np.int32,
        )
        if len(points) > 1:
            cv2.polylines(overlay, [points], False, (0, 215, 255), 2)
        if snapshot.current_position is not None:
            current = (
                int(snapshot.current_position[0] - origin_x),
                int(snapshot.current_position[1] - origin_y),
            )
            cv2.circle(overlay, current, 5, (0, 255, 0), -1)
            cv2.circle(overlay, current, 7, (0, 0, 255), 1)
        return overlay


__all__ = ["Poe2StitchingArchive", "STITCHING_SCHEMA_VERSION"]
