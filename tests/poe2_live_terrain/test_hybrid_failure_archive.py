import json
from types import SimpleNamespace

import numpy as np

from auto_modules.features.poe2.live_terrain.capture_samples import CaptureEvidence
from auto_modules.features.poe2.live_terrain.contracts import CaptureMetadata, TerrainSnapshot
from auto_modules.features.poe2.live_terrain.hybrid_failure_archive import (
    Poe2HybridFailureArchive,
)


def terrain_snapshot():
    state = np.ones((12, 14), dtype=np.int8)
    known = np.ones_like(state, dtype=np.uint8)
    return TerrainSnapshot(
        metadata=CaptureMetadata(
            area_id="MapTest",
            area_hash="A1",
            instance_id="MapTest:A1",
            width=14,
            height=12,
            captured_at="2026-09-22T00:00:00+00:00",
        ),
        raw_cells=np.zeros_like(state, dtype=np.uint8),
        cell_state=state,
        known_mask=known,
        wall_layer=np.zeros_like(state, dtype=np.uint8),
        explored_map=known * 255,
    )


def evidence():
    raw = np.full((20, 30, 3), 17, dtype=np.uint8)
    mask = np.zeros((20, 30), dtype=np.uint8)
    mask[4:8, 6:20] = 255
    return CaptureEvidence(
        captured_at="2026-09-22T00:00:01+00:00",
        raw=raw,
        processed=raw,
        feature=mask,
        wall_mask=mask,
        monitor_config={},
    )


def test_failure_archive_saves_visuals_terrain_and_localization_state(tmp_path):
    archive = Poe2HybridFailureArchive(tmp_path)
    state = SimpleNamespace(
        mode="recovery_required",
        source="failed",
        confidence=0.0,
        position=None,
        latest_confirmed_position=(12.0, 18.0),
        trajectory=((12.0, 18.0),),
        reason="absolute_registration_failed",
        recovery_revision=4,
        memory_read_count=4,
        diagnostics={"best_score": 0.42, "best_anchor_error": 19.05},
        frame_elapsed_ms=5367.0,
    )
    experiment = SimpleNamespace(
        session=SimpleNamespace(
            last_evidence=evidence(),
            last_frame=SimpleNamespace(frame_id=8, captured_at_ms=1234, local_player=(15.0, 10.0)),
        ),
        controller=SimpleNamespace(last_confirmed=None),
    )

    destination = archive.record(
        experiment=experiment,
        state=state,
        snapshot=terrain_snapshot(),
    )

    assert (destination / "raw.png").is_file()
    assert (destination / "processed.png").is_file()
    assert (destination / "wall_mask.png").is_file()
    assert (destination / "terrain.png").is_file()
    manifest = json.loads((destination / "localization_failure.json").read_text(encoding="utf-8"))
    assert manifest["reason"] == "absolute_registration_failed"
    assert manifest["recovery_revision"] == 4
    assert manifest["memory_read_count"] == 4
    assert manifest["diagnostics"]["best_anchor_error"] == 19.05
