from __future__ import annotations

import json
from types import MappingProxyType

import cv2
import numpy as np
import pytest

from auto_modules.features.poe2.live_terrain.contracts import CaptureMetadata, TerrainSnapshot
from auto_modules.features.poe2.live_terrain.stitching_archive import Poe2StitchingArchive
from auto_modules.features.poe2.live_terrain.stitching_session import Poe2StitchingSnapshot

from .test_stitching_session import _evidence


def _snapshot(*, with_trajectory: bool = True) -> Poe2StitchingSnapshot:
    trajectory = ((100, 100), (104, 98)) if with_trajectory else ()
    return Poe2StitchingSnapshot(
        state="paused",
        map_image=np.full((24, 32, 3), 60, dtype=np.uint8),
        map_origin=(90, 88),
        current_position=(104, 98) if with_trajectory else None,
        trajectory=trajectory,
        statistics=MappingProxyType({"total_frames": 2, "successful_matches": 1}),
        draw_scale=2.0,
        player_position=(4.0, 3.0),
        capture_size=(10, 8),
    )


def _terrain() -> TerrainSnapshot:
    metadata = CaptureMetadata(
        "MapFlotsam",
        "hash",
        "MapFlotsam:hash",
        3,
        2,
        "2026-09-21T00:00:00+00:00",
    )
    return TerrainSnapshot(
        metadata,
        np.zeros((2, 3), dtype=np.uint8),
        np.ones((2, 3), dtype=np.int8),
        np.full((2, 3), 255, dtype=np.uint8),
        np.zeros((2, 3), dtype=np.uint8),
        np.full((2, 3), 255, dtype=np.uint8),
    )


def test_archive_publishes_complete_stitching_evidence(tmp_path):
    archive = Poe2StitchingArchive(tmp_path / "sessions")

    path = archive.save(_snapshot(), _evidence(), terrain=_terrain())

    assert path.parent == archive.root
    expected = {
        "stitched_map.png",
        "stitched_map_overlay.png",
        "raw.png",
        "processed.png",
        "feature.png",
        "wall_mask.png",
        "fog_mask.png",
        "terrain.png",
        "session.json",
    }
    assert {item.name for item in path.iterdir()} == expected
    payload = json.loads((path / "session.json").read_text(encoding="utf-8"))
    assert payload["schema_version"] == 1
    assert payload["trajectory"] == [[100, 100], [104, 98]]
    assert payload["current_position"] == [104, 98]
    assert payload["map_origin"] == [90, 88]
    assert payload["statistics"]["successful_matches"] == 1
    assert payload["monitor_config"]["binding"]["player_marker_position"] == [4, 3]
    assert payload["terrain"]["instance_id"] == "MapFlotsam:hash"
    assert cv2.imread(str(path / "stitched_map.png"), cv2.IMREAD_COLOR).shape == (24, 32, 3)


def test_archive_rejects_empty_session_without_publishing_directory(tmp_path):
    archive = Poe2StitchingArchive(tmp_path / "sessions")

    with pytest.raises(RuntimeError, match="no accepted stitching frame"):
        archive.save(_snapshot(with_trajectory=False), _evidence())

    assert not archive.root.exists()
