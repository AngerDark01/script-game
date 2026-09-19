import pytest
import numpy as np

from auto_modules.features.poe2.live_terrain.contracts import (
    CaptureMetadata,
    TerrainCaptureError,
    TerrainSessionState,
    TerrainSnapshot,
)
from auto_modules.features.poe2.live_terrain.service import Poe2TerrainService


class FakeAdapter:
    def __init__(self, snapshot=None, error=None):
        self.snapshot_value = snapshot
        self.error = error
        self.initialize_calls = 0
        self.capture_calls = 0

    def initialize(self):
        self.initialize_calls += 1
        if self.error:
            raise self.error

    def capture(self):
        self.capture_calls += 1
        if self.error:
            raise self.error
        return self.snapshot_value


def snapshot_factory():
    metadata = CaptureMetadata("A", "h", "A:h", 1, 1, "2026-09-19T00:00:00+00:00")
    return TerrainSnapshot(
        metadata,
        np.zeros((1, 1), dtype=np.uint8),
        np.zeros((1, 1), dtype=np.int8),
        np.zeros((1, 1), dtype=np.uint8),
        np.zeros((1, 1), dtype=np.uint8),
        np.zeros((1, 1), dtype=np.uint8),
    )


def test_capture_requires_initialization_and_success_replaces_snapshot():
    adapter = FakeAdapter(snapshot_factory())
    service = Poe2TerrainService(adapter)
    with pytest.raises(TerrainCaptureError):
        service.capture()
    service.initialize()
    snapshot = service.capture()
    assert snapshot is adapter.snapshot_value
    assert service.state is TerrainSessionState.CAPTURED


def test_failed_capture_clears_old_snapshot():
    adapter = FakeAdapter(snapshot_factory())
    service = Poe2TerrainService(adapter)
    service.initialize()
    service.capture()
    adapter.error = RuntimeError("game process changed; run init again")
    with pytest.raises(RuntimeError):
        service.capture()
    assert service.snapshot() is None
    assert service.state is TerrainSessionState.ERROR


def test_successful_capture_can_archive_converted_snapshot(tmp_path):
    from auto_modules.features.poe2.live_terrain.debug_archive import TerrainDebugArchive

    adapter = FakeAdapter(snapshot_factory())
    archive = TerrainDebugArchive(tmp_path / "terrain")
    service = Poe2TerrainService(adapter, archive=archive)
    service.initialize()
    service.capture()

    assert archive.npz_path.is_file()
    assert archive.manifest_path.is_file()
