import numpy as np
import pytest

from auto_modules.features.poe2.live_terrain.contracts import (
    CaptureMetadata,
    TerrainSnapshot,
)


def _snapshot(**overrides):
    metadata = CaptureMetadata(
        area_id="Area",
        area_hash="hash",
        instance_id="Area:hash",
        width=2,
        height=2,
        captured_at="2026-09-19T00:00:00+00:00",
        **overrides,
    )
    return TerrainSnapshot(
        metadata,
        np.zeros((2, 2), dtype=np.uint8),
        np.zeros((2, 2), dtype=np.int8),
        np.full((2, 2), 255, dtype=np.uint8),
        np.zeros((2, 2), dtype=np.uint8),
        np.full((2, 2), 255, dtype=np.uint8),
    )


def test_snapshot_copies_and_freezes_arrays():
    snapshot = _snapshot()
    assert snapshot.raw_cells.flags.writeable is False
    with pytest.raises(ValueError):
        snapshot.raw_cells[0, 0] = 1


def test_snapshot_rejects_shape_or_state_contract_violations():
    metadata = CaptureMetadata(
        area_id="Area", area_hash="hash", instance_id="Area:hash", width=2,
        height=2, captured_at="2026-09-19T00:00:00+00:00",
    )
    with pytest.raises(ValueError, match="shape"):
        TerrainSnapshot(
            metadata,
            np.zeros((1, 2), dtype=np.uint8),
            np.zeros((2, 2), dtype=np.int8),
            np.zeros((2, 2), dtype=np.uint8),
            np.zeros((2, 2), dtype=np.uint8),
            np.zeros((2, 2), dtype=np.uint8),
        )
