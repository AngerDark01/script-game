from __future__ import annotations

import hashlib
import json
import os
import subprocess

import cv2
import numpy as np
import pytest

from auto_modules.features.poe2.live_terrain.capture_samples import (
    CaptureEvidence,
    CaptureSampleArchive,
)
from auto_modules.features.poe2.live_terrain.contracts import CaptureMetadata, TerrainSnapshot
from auto_modules.features.poe2.live_terrain.player_position import PlayerPositionSample


def _evidence() -> CaptureEvidence:
    return CaptureEvidence(
        captured_at="2026-09-21T06:30:00+00:00",
        raw=np.full((6, 8, 3), 10, dtype=np.uint8),
        processed=np.full((6, 8, 3), 20, dtype=np.uint8),
        feature=np.full((6, 8), 30, dtype=np.uint8),
        monitor_config={"profile_id": "test", "binding": {"rect": {"left": 1}}},
        wall_mask=np.full((6, 8), 40, dtype=np.uint8),
        fog_mask=np.full((6, 8), 50, dtype=np.uint8),
        raw_gray=np.full((6, 8), 60, dtype=np.uint8),
    )


def _terrain() -> TerrainSnapshot:
    metadata = CaptureMetadata(
        "MapFlotsam",
        "C121287D",
        "MapFlotsam:C121287D",
        4,
        3,
        "2026-09-21T06:29:00+00:00",
    )
    return TerrainSnapshot(
        metadata,
        np.array([[0, 0, 0, 0], [0, 1, 1, 0], [0, 0, 0, 0]], dtype=np.uint8),
        np.array([[0, 0, 0, 0], [0, 1, 1, 0], [0, 0, 0, 0]], dtype=np.int8),
        np.full((3, 4), 255, dtype=np.uint8),
        np.array([[255, 255, 255, 255], [255, 0, 0, 255], [255, 255, 255, 255]], dtype=np.uint8),
        np.full((3, 4), 255, dtype=np.uint8),
    )


def test_capture_evidence_detaches_and_freezes_arrays_and_config():
    raw = np.ones((2, 3, 3), dtype=np.uint8)
    config = {"binding": {"rect": {"left": 10}}}
    evidence = CaptureEvidence(
        captured_at="2026-09-21T06:30:00+00:00",
        raw=raw,
        processed=raw + 1,
        feature=np.ones((2, 3), dtype=np.uint8),
        monitor_config=config,
    )
    raw[:] = 99
    config["binding"]["rect"]["left"] = 20

    assert evidence.raw.tolist() == np.ones((2, 3, 3), dtype=np.uint8).tolist()
    assert evidence.monitor_config["binding"]["rect"]["left"] == 10
    assert evidence.raw.flags.writeable is False
    with pytest.raises(ValueError):
        evidence.raw[0, 0, 0] = 4


def test_sample_archive_saves_synchronized_images_manifest_and_history(tmp_path):
    archive = CaptureSampleArchive(tmp_path / "samples")
    position = PlayerPositionSample.from_world(
        world=(10.0, 20.0, -3.0),
        captured_at="2026-09-21T06:29:30+00:00",
        area_instance="MapFlotsam:C121287D",
    )
    record = archive.save(_evidence(), terrain=_terrain(), player_position=position)

    assert record.path.parent == tmp_path / "samples"
    assert set(record.images) == {
        "raw",
        "processed",
        "feature",
        "wall_mask",
        "fog_mask",
        "raw_gray",
        "terrain",
    }
    manifest = json.loads((record.path / "sample.json").read_text(encoding="utf-8"))
    assert manifest["terrain"]["instance_id"] == "MapFlotsam:C121287D"
    assert manifest["monitor_config"]["profile_id"] == "test"
    assert manifest["player_position"]["status"] == "available"
    assert manifest["player_position"]["area_instance"] == "MapFlotsam:C121287D"
    assert manifest["player_position"]["grid"] == pytest.approx([0.92, 1.84])
    assert manifest["player_position"]["terrain_grid"] == pytest.approx([0.92, 1.84])
    assert manifest["terrain"]["coordinate_space"] == "native"
    assert "orientation" not in manifest["terrain"]
    for layer, details in manifest["images"].items():
        payload = (record.path / details["file"]).read_bytes()
        assert details["sha256"] == hashlib.sha256(payload).hexdigest()
        assert cv2.imread(str(record.path / details["file"]), cv2.IMREAD_UNCHANGED) is not None

    loaded = archive.load(record.path)
    assert loaded.path == record.path
    assert archive.list_samples() == (loaded,)


def test_sample_archive_ignores_legacy_direction_and_keeps_native_coordinates(tmp_path):
    archive = CaptureSampleArchive(tmp_path / "samples")
    base = _evidence()
    config = dict(base.monitor_config)
    config.update(
        {
            "map_rotation": 90,
            "map_flip_horizontal": True,
            "map_flip_vertical": True,
        }
    )
    evidence = CaptureEvidence(
        captured_at=base.captured_at,
        raw=base.raw,
        processed=base.processed,
        feature=base.feature,
        monitor_config=config,
    )
    position = PlayerPositionSample.from_world(
        world=(10.0, 20.0, -3.0),
        captured_at="2026-09-21T06:29:30+00:00",
        area_instance="MapFlotsam:C121287D",
    )

    record = archive.save(evidence, terrain=_terrain(), player_position=position)
    terrain_image = cv2.imread(str(record.images["terrain"]), cv2.IMREAD_COLOR)
    manifest = record.manifest
    assert terrain_image.shape[:2] == (3, 4)
    assert manifest["terrain"]["width"] == terrain_image.shape[1]
    assert manifest["terrain"]["height"] == terrain_image.shape[0]
    assert manifest["terrain"]["native_width"] == 4
    assert manifest["terrain"]["native_height"] == 3
    assert manifest["player_position"]["grid"] == pytest.approx(position.grid)
    assert manifest["player_position"]["terrain_grid"] == pytest.approx(position.grid)
    assert manifest["terrain"]["coordinate_space"] == "native"
    assert "orientation" not in manifest["terrain"]


def test_sample_archive_allows_missing_terrain_without_borrowing_old_image(tmp_path):
    archive = CaptureSampleArchive(tmp_path / "samples")
    first = archive.save(_evidence(), terrain=_terrain())
    second = archive.save(_evidence(), terrain=None)

    assert first.path != second.path
    assert "terrain" not in second.images
    assert second.manifest["terrain"] == {"status": "missing", "reason": "no current terrain snapshot"}
    assert not (second.path / "terrain.png").exists()


def test_sample_archive_keeps_legacy_required_layers_compatible(tmp_path):
    archive = CaptureSampleArchive(tmp_path / "samples")
    evidence = CaptureEvidence(
        captured_at="2026-09-21T06:30:00+00:00",
        raw=np.full((6, 8, 3), 10, dtype=np.uint8),
        processed=np.full((6, 8, 3), 20, dtype=np.uint8),
        feature=np.full((6, 8), 30, dtype=np.uint8),
        monitor_config={"profile_id": "legacy"},
    )

    record = archive.save(evidence)

    assert set(record.images) == {"raw", "processed", "feature"}


def test_sample_archive_does_not_publish_partial_directory(tmp_path, monkeypatch):
    archive = CaptureSampleArchive(tmp_path / "samples")
    calls = 0
    original = archive._write_png

    def fail_second(path, image):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError("disk full")
        return original(path, image)

    monkeypatch.setattr(archive, "_write_png", fail_second)
    with pytest.raises(OSError, match="disk full"):
        archive.save(_evidence(), terrain=_terrain())

    assert archive.list_samples() == ()
    assert list((tmp_path / "samples").glob("*")) == []


@pytest.mark.skipif(os.name != "nt", reason="Windows ACL regression")
def test_sample_directory_inherits_parent_acl_on_windows(tmp_path):
    archive = CaptureSampleArchive(tmp_path / "samples")
    record = archive.save(_evidence(), terrain=_terrain())

    result = subprocess.run(
        ["icacls", str(record.path)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=True,
    )

    assert "(I)" in result.stdout
