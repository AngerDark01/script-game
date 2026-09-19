import json

import numpy as np
import pytest

from auto_modules.features.poe2.live_terrain.native_grid import load_native_grid
from auto_modules.features.poe2.live_terrain.contracts import TerrainCaptureError


def _write_grid(path, **overrides):
    payload = {
        "raw_cells": np.array([[0, 1], [2, 15]], dtype=np.uint8),
        "cell_state": np.array([[0, 1], [1, -1]], dtype=np.int8),
        "known_mask": np.array([[255, 255], [255, 0]], dtype=np.uint8),
        "wall_layer": np.array([[255, 0], [0, 255]], dtype=np.uint8),
        "explored_map": np.array([[255, 255], [255, 0]], dtype=np.uint8),
        "metadata_json": json.dumps({
            "area_id": "Area",
            "area_hash": "hash",
            "instance_id": "Area:hash",
            "width": 2,
            "height": 2,
            "captured_at": "2026-09-19T00:00:00+00:00",
            "tool": "manual-live-terrain-capture",
        }),
    }
    payload.update(overrides)
    np.savez(path, **payload)


def test_load_native_grid_preserves_yx_order_and_semantics(tmp_path):
    path = tmp_path / "native_grid.npz"
    _write_grid(path)
    snapshot = load_native_grid(path)
    assert snapshot.raw_cells.tolist() == [[0, 1], [2, 15]]
    assert snapshot.cell_state[1, 1] == -1
    assert snapshot.wall_layer[0, 0] == 255
    assert snapshot.metadata.width == 2


def test_load_native_grid_rejects_missing_key(tmp_path):
    path = tmp_path / "native_grid.npz"
    _write_grid(path)
    with np.load(path, allow_pickle=False) as data:
        values = {key: data[key] for key in data.files if key != "wall_layer"}
    np.savez(path, **values)
    with pytest.raises(TerrainCaptureError, match="missing keys"):
        load_native_grid(path)


def test_load_native_grid_rejects_pickle_payload(tmp_path):
    path = tmp_path / "native_grid.npz"
    np.savez(path, metadata_json=np.array({"unsafe": True}, dtype=object))
    with pytest.raises(TerrainCaptureError):
        load_native_grid(path)
