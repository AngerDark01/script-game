from datetime import datetime, timezone

import pytest

from auto_modules.features.poe2.live_terrain.experimental.hybrid_localization.memory_anchor import (
    Poe2MemoryAnchorProvider,
)
from auto_modules.features.poe2.live_terrain.orientation import TerrainOrientation
from auto_modules.features.poe2.live_terrain.player_position import (
    PlayerPositionError,
    PlayerPositionSample,
)


class PositionSourceFake:
    def __init__(self, sample=None, error=None):
        self.sample = sample
        self.error = error
        self.expected_instances = []

    def read_once(self, expected_instance_id):
        self.expected_instances.append(expected_instance_id)
        if self.error is not None:
            raise self.error
        return self.sample


def test_memory_anchor_transforms_native_grid_into_reference_space():
    captured_at = "2026-09-22T00:00:01+00:00"
    source = PositionSourceFake(
        PlayerPositionSample(
            world=(100.0, 200.0, 0.0),
            grid=(20.0, 30.0),
            captured_at=captured_at,
            area_instance="Map:A1",
        )
    )
    provider = Poe2MemoryAnchorProvider(
        source,
        TerrainOrientation(rotation=90, flip_horizontal=True),
        native_shape=(100, 200),
        clock_ms=lambda: 0,
    )

    anchor = provider.read_once("Map:A1")

    expected = provider.orientation.transform_point((20.0, 30.0), (100, 200))
    assert anchor.position == expected
    assert anchor.area_instance == "Map:A1"
    assert anchor.captured_at_ms == int(
        datetime.fromisoformat(captured_at).timestamp() * 1000
    )
    assert anchor.source == "poe2_memory"
    assert provider.read_count == 1
    assert source.expected_instances == ["Map:A1"]


def test_memory_anchor_counts_failed_read_and_propagates_source_error():
    source = PositionSourceFake(error=PlayerPositionError("unavailable"))
    provider = Poe2MemoryAnchorProvider(
        source,
        TerrainOrientation(),
        native_shape=(100, 200),
        clock_ms=lambda: 1234,
    )

    with pytest.raises(PlayerPositionError, match="unavailable"):
        provider.read_once("Map:A1")

    assert provider.read_count == 1


def test_memory_anchor_uses_clock_when_sample_timestamp_is_missing():
    source = PositionSourceFake(
        PlayerPositionSample(
            world=(0.0, 0.0, 0.0),
            grid=(0.0, 0.0),
            captured_at="",
            area_instance="Map:A1",
        )
    )
    provider = Poe2MemoryAnchorProvider(
        source,
        TerrainOrientation(),
        native_shape=(10, 10),
        clock_ms=lambda: 1234,
    )

    assert provider.read_once("Map:A1").captured_at_ms == 1234
