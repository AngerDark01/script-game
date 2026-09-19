import numpy as np

from auto_modules.features.poe2.live_terrain.contracts import CaptureMetadata, TerrainSnapshot
from auto_modules.features.poe2.live_terrain.memory_store import MemoryTerrainStore


def _snapshot():
    metadata = CaptureMetadata("A", "h", "A:h", 1, 1, "2026-09-19T00:00:00+00:00")
    return TerrainSnapshot(
        metadata,
        np.zeros((1, 1), dtype=np.uint8),
        np.zeros((1, 1), dtype=np.int8),
        np.zeros((1, 1), dtype=np.uint8),
        np.zeros((1, 1), dtype=np.uint8),
        np.zeros((1, 1), dtype=np.uint8),
    )


def test_memory_store_replaces_and_clears_only_in_memory():
    store = MemoryTerrainStore()
    snapshot = _snapshot()
    assert store.replace(snapshot) is snapshot
    assert store.snapshot() is snapshot
    store.clear()
    assert store.snapshot() is None
