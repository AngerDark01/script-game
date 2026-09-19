import json

import numpy as np

from auto_modules.features.poe2.live_terrain.contracts import CaptureMetadata, TerrainSnapshot
from auto_modules.features.poe2.live_terrain.debug_archive import TerrainDebugArchive


def _snapshot():
    metadata = CaptureMetadata(
        "Area",
        "hash",
        "Area:hash",
        2,
        1,
        "2026-09-19T00:00:00+00:00",
    )
    return TerrainSnapshot(
        metadata,
        np.array([[1, 2]], dtype=np.uint8),
        np.array([[-1, 1]], dtype=np.int8),
        np.array([[255, 0]], dtype=np.uint8),
        np.array([[0, 1]], dtype=np.uint8),
        np.array([[255, 255]], dtype=np.uint8),
    )


def test_debug_archive_writes_converted_arrays_and_manifest(tmp_path):
    archive = TerrainDebugArchive(tmp_path / "terrain")
    path = archive.save(_snapshot())

    assert path == tmp_path / "terrain" / "latest.npz"
    assert path.is_file()
    manifest = json.loads(archive.manifest_path.read_text(encoding="utf-8"))
    assert manifest["tool"] == "auto-modules-poe2-terrain-debug-archive"
    assert manifest["instance_id"] == "Area:hash"
    with np.load(path, allow_pickle=False) as data:
        assert data["cell_state"].tolist() == [[-1, 1]]
        assert data["metadata_json"].ndim == 0
