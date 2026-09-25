"""Persist synchronized PoE2 screenshot evidence for manual comparison."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import shutil
from types import MappingProxyType
from typing import Any, Mapping

import cv2
import numpy as np

from .contracts import TerrainSnapshot
from .player_position import PlayerPositionSample


SAMPLE_SCHEMA_VERSION = 1
IMAGE_LAYERS = (
    "raw",
    "processed",
    "feature",
    "wall_mask",
    "fog_mask",
    "raw_gray",
    "terrain",
)


def _readonly_image(value: Any, name: str) -> np.ndarray:
    image = np.array(value, copy=True, order="C")
    if image.size == 0 or image.ndim not in (2, 3):
        raise ValueError(f"{name} must be a non-empty 2D or 3D image")
    if image.dtype != np.uint8:
        image = np.clip(image, 0, 255).astype(np.uint8)
    image.setflags(write=False)
    return image


def _json_payload(value: Mapping[str, Any]) -> dict[str, Any]:
    return json.loads(json.dumps(deepcopy(dict(value)), ensure_ascii=False, default=str))


@dataclass(frozen=True)
class CaptureEvidence:
    """Visual layers that are guaranteed to originate from one captured frame."""

    captured_at: str
    raw: np.ndarray
    processed: np.ndarray
    feature: np.ndarray
    monitor_config: Mapping[str, Any]
    wall_mask: np.ndarray | None = None
    fog_mask: np.ndarray | None = None
    raw_gray: np.ndarray | None = None

    def __post_init__(self) -> None:
        try:
            datetime.fromisoformat(str(self.captured_at).replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError("captured_at must be an ISO timestamp") from exc
        object.__setattr__(self, "raw", _readonly_image(self.raw, "raw"))
        object.__setattr__(self, "processed", _readonly_image(self.processed, "processed"))
        object.__setattr__(self, "feature", _readonly_image(self.feature, "feature"))
        for name in ("wall_mask", "fog_mask", "raw_gray"):
            value = getattr(self, name)
            if value is not None:
                object.__setattr__(self, name, _readonly_image(value, name))
        object.__setattr__(self, "monitor_config", MappingProxyType(_json_payload(self.monitor_config)))


@dataclass(frozen=True)
class CaptureSampleRecord:
    path: Path
    manifest: Mapping[str, Any]
    images: Mapping[str, Path]

    def __post_init__(self) -> None:
        object.__setattr__(self, "path", Path(self.path).resolve())
        object.__setattr__(self, "manifest", MappingProxyType(deepcopy(dict(self.manifest))))
        object.__setattr__(self, "images", MappingProxyType(dict(self.images)))


def _safe_name(value: str, fallback: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "-", str(value)).strip("-._")
    return cleaned or fallback


def terrain_preview(snapshot: TerrainSnapshot, config: Mapping[str, Any]) -> np.ndarray:
    del config
    cell_state = snapshot.cell_state
    known_mask = snapshot.known_mask
    walkable = (cell_state == 1) & (known_mask > 0)
    padded = np.pad(walkable, 1, mode="constant", constant_values=False)
    kernel = np.ones((3, 3), dtype=np.uint8)
    dilated = cv2.dilate(padded.astype(np.uint8), kernel)[1:-1, 1:-1] > 0
    eroded = cv2.erode(padded.astype(np.uint8), kernel)[1:-1, 1:-1] > 0
    edge = dilated & ~eroded
    image = np.zeros((*walkable.shape, 3), dtype=np.uint8)
    image[walkable] = (60, 60, 60)
    image[edge] = (235, 235, 235)
    return image

class CaptureSampleArchive:
    """Atomically publish complete manual-comparison sample directories."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root).expanduser().resolve()

    def save(
        self,
        evidence: CaptureEvidence,
        *,
        terrain: TerrainSnapshot | None = None,
        player_position: PlayerPositionSample | None = None,
    ) -> CaptureSampleRecord:
        if not isinstance(evidence, CaptureEvidence):
            raise TypeError("evidence must be CaptureEvidence")
        self.root.mkdir(parents=True, exist_ok=True)
        destination = self._destination(evidence, terrain)
        temporary = self._create_temporary_directory()
        try:
            image_details: dict[str, dict[str, Any]] = {}
            image_details["raw"] = self._write_png(temporary / "raw.png", evidence.raw)
            image_details["processed"] = self._write_png(
                temporary / "processed.png", evidence.processed
            )
            image_details["feature"] = self._write_png(
                temporary / "feature.png", evidence.feature
            )
            for layer in ("wall_mask", "fog_mask", "raw_gray"):
                image = getattr(evidence, layer)
                if image is not None:
                    image_details[layer] = self._write_png(
                        temporary / f"{layer}.png",
                        image,
                    )
            terrain_details: dict[str, Any]
            if terrain is None:
                terrain_details = {
                    "status": "missing",
                    "reason": "no current terrain snapshot",
                }
            else:
                preview = terrain_preview(terrain, evidence.monitor_config)
                image_details["terrain"] = self._write_png(
                    temporary / "terrain.png",
                    preview,
                )
                terrain_details = {
                    "status": "available",
                    "area_id": terrain.metadata.area_id,
                    "area_hash": terrain.metadata.area_hash,
                    "instance_id": terrain.metadata.instance_id,
                    "width": int(preview.shape[1]),
                    "height": int(preview.shape[0]),
                    "native_width": terrain.metadata.width,
                    "native_height": terrain.metadata.height,
                    "coordinate_space": "native",
                    "captured_at": terrain.metadata.captured_at,
                }
            if player_position is None:
                player_position_details: dict[str, Any] = {
                    "status": "missing",
                    "reason": "no current player position sample",
                }
            else:
                if (
                    terrain is not None
                    and player_position.area_instance != terrain.metadata.instance_id
                ):
                    raise ValueError("player position and terrain must use the same area instance")
                player_position_details = {
                    "status": "available",
                    "area_instance": player_position.area_instance,
                    "captured_at": player_position.captured_at,
                    "world": list(player_position.world),
                    "grid": list(player_position.grid),
                }
                if terrain is not None:
                    player_position_details["terrain_grid"] = list(player_position.grid)
            manifest = {
                "schema_version": SAMPLE_SCHEMA_VERSION,
                "saved_at": datetime.now(timezone.utc).isoformat(),
                "captured_at": evidence.captured_at,
                "monitor_config": _json_payload(evidence.monitor_config),
                "terrain": terrain_details,
                "player_position": player_position_details,
                "images": image_details,
            }
            (temporary / "sample.json").write_text(
                json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            os.replace(temporary, destination)
        except Exception:
            shutil.rmtree(temporary, ignore_errors=True)
            raise
        return self.load(destination)

    def _create_temporary_directory(self) -> Path:
        # tempfile.mkdtemp(mode=0o700) installs an owner-only DACL on Windows.
        # A normal mkdir inherits the shared workspace ACL from the samples root.
        for _attempt in range(100):
            candidate = self.root / f".sample-{secrets.token_hex(8)}"
            try:
                candidate.mkdir()
            except FileExistsError:
                continue
            return candidate
        raise FileExistsError("could not allocate a unique sample directory")

    def list_samples(self) -> tuple[CaptureSampleRecord, ...]:
        if not self.root.is_dir():
            return ()
        records: list[CaptureSampleRecord] = []
        for path in sorted(self.root.iterdir()):
            if not path.is_dir() or path.name.startswith("."):
                continue
            try:
                records.append(self.load(path))
            except (OSError, ValueError, TypeError, json.JSONDecodeError):
                continue
        return tuple(records)

    def load(self, path: str | Path) -> CaptureSampleRecord:
        directory = Path(path).expanduser().resolve()
        try:
            directory.relative_to(self.root)
        except ValueError as exc:
            raise ValueError("sample path must be inside archive root") from exc
        manifest_path = directory / "sample.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if not isinstance(manifest, dict) or manifest.get("schema_version") != SAMPLE_SCHEMA_VERSION:
            raise ValueError("sample manifest has an unsupported schema")
        details = manifest.get("images")
        if not isinstance(details, dict):
            raise ValueError("sample manifest does not contain images")
        images: dict[str, Path] = {}
        for layer, item in details.items():
            if layer not in IMAGE_LAYERS or not isinstance(item, dict):
                continue
            image_path = directory / str(item.get("file", ""))
            if not image_path.is_file():
                raise ValueError(f"sample image is missing: {layer}")
            images[layer] = image_path
        if not {"raw", "processed", "feature"}.issubset(images):
            raise ValueError("sample is missing required screenshot layers")
        return CaptureSampleRecord(directory, manifest, images)

    def _destination(
        self,
        evidence: CaptureEvidence,
        terrain: TerrainSnapshot | None,
    ) -> Path:
        stamp = datetime.fromisoformat(evidence.captured_at.replace("Z", "+00:00")).strftime(
            "%Y%m%d-%H%M%S-%f"
        )
        area_id = terrain.metadata.area_id if terrain is not None else "no-terrain"
        area_hash = terrain.metadata.area_hash if terrain is not None else "none"
        base = f"{stamp}-{_safe_name(area_id, 'area')}-{_safe_name(area_hash, 'hash')}"
        candidate = self.root / base
        suffix = 2
        while candidate.exists():
            candidate = self.root / f"{base}-{suffix}"
            suffix += 1
        return candidate

    @staticmethod
    def _write_png(path: Path, image: np.ndarray) -> dict[str, Any]:
        success, encoded = cv2.imencode(".png", np.asarray(image))
        if not success:
            raise OSError(f"could not encode image: {path.name}")
        payload = encoded.tobytes()
        path.write_bytes(payload)
        array = np.asarray(image)
        return {
            "file": path.name,
            "width": int(array.shape[1]),
            "height": int(array.shape[0]),
            "channels": int(array.shape[2]) if array.ndim == 3 else 1,
            "dtype": str(array.dtype),
            "sha256": hashlib.sha256(payload).hexdigest(),
        }


__all__ = ["CaptureEvidence", "CaptureSampleArchive", "CaptureSampleRecord"]
