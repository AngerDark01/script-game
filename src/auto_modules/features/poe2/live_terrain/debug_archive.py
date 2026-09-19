"""Explicit local test archive for converted PoE2 terrain snapshots."""

from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path

import numpy as np

from .contracts import TerrainSnapshot
from .logging_utils import get_terrain_logger


class TerrainDebugArchive:
    """Persist the latest converted snapshot for manual validation only."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root).expanduser().resolve()
        self._logger = get_terrain_logger()

    @property
    def npz_path(self) -> Path:
        return self.root / "latest.npz"

    @property
    def manifest_path(self) -> Path:
        return self.root / "latest.json"

    def save(self, snapshot: TerrainSnapshot) -> Path:
        self.root.mkdir(parents=True, exist_ok=True)
        npz_path = self.npz_path
        npz_tmp = self.root / "latest.npz.tmp"
        manifest_tmp = self.root / "latest.json.tmp"
        self._logger.info(
            "step=archive.start path=%s shape=%sx%s",
            npz_path,
            snapshot.metadata.height,
            snapshot.metadata.width,
        )
        with npz_tmp.open("wb") as handle:
            np.savez_compressed(
                handle,
                raw_cells=snapshot.raw_cells,
                cell_state=snapshot.cell_state,
                known_mask=snapshot.known_mask,
                wall_layer=snapshot.wall_layer,
                explored_map=snapshot.explored_map,
                metadata_json=json.dumps(
                    {
                        **dict(snapshot.metadata.extra),
                        "area_id": snapshot.metadata.area_id,
                        "area_hash": snapshot.metadata.area_hash,
                        "instance_id": snapshot.metadata.instance_id,
                        "width": snapshot.metadata.width,
                        "height": snapshot.metadata.height,
                        "captured_at": snapshot.metadata.captured_at,
                        "raw_sha256": snapshot.metadata.raw_sha256,
                        "tool": snapshot.metadata.tool,
                    },
                    ensure_ascii=False,
                    default=str,
                ),
            )
        os.replace(npz_tmp, npz_path)

        manifest = {
            "tool": "auto-modules-poe2-terrain-debug-archive",
            "saved_at": datetime.now(timezone.utc).isoformat(),
            "source_tool": snapshot.metadata.tool,
            "area_id": snapshot.metadata.area_id,
            "area_hash": snapshot.metadata.area_hash,
            "instance_id": snapshot.metadata.instance_id,
            "width": snapshot.metadata.width,
            "height": snapshot.metadata.height,
            "captured_at": snapshot.metadata.captured_at,
            "native_grid": str(npz_path.resolve()),
        }
        manifest_tmp.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        os.replace(manifest_tmp, self.manifest_path)
        self._logger.info("step=archive.success manifest=%s", self.manifest_path)
        return npz_path
