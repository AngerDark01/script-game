from __future__ import annotations

import numpy as np

from auto_modules.core.localization.frame_displacement import FrameDisplacement
from auto_modules.features.poe2.live_terrain.experimental.hybrid_localization.models import HybridFrame, PositionAnchor
from auto_modules.features.poe2.live_terrain.experimental.multiframe_localization.archive import MultiframeArchive
from auto_modules.features.poe2.live_terrain.experimental.multiframe_localization.models import MultiFrameEvidence
from auto_modules.features.poe2.live_terrain.terrain_reference import TerrainReference
from tools.debug.poe2_multiframe_localization_probe import replay_archive


def test_probe_reconstructs_evidence_and_reruns_both_strategies(tmp_path):
    evidence = []
    for frame_id in range(1, 5):
        wall = np.zeros((16, 16), dtype=np.uint8)
        wall[3:13, 5] = 255
        frame = HybridFrame(frame_id, frame_id * 100, wall, (8.0, 8.0))
        evidence.append(
            MultiFrameEvidence(
                frame,
                FrameDisplacement((3.0, 0.0), 0.9, 3.0, True, "accepted"),
                (-3.0 * (frame_id - 1), 0.0),
                True,
                0,
            )
        )
    walkable = np.zeros((80, 80), dtype=bool)
    walkable[20:60, 20:60] = True
    reference = TerrainReference(
        walkable,
        np.where(walkable, 0, 255).astype(np.uint8),
        np.full((80, 80), 255, dtype=np.uint8),
        80,
        80,
        {"instance_id": "Map:A"},
    )
    target = MultiframeArchive().save(
        tmp_path / "run",
        evidence=tuple(evidence),
        anchor=PositionAnchor((40.0, 40.0), "Map:A", 100, "memory"),
        instance_id="Map:A",
        reference=reference,
    )

    report = replay_archive(target, strategy="both")

    assert report["evidence_count"] == 4
    assert report["coordinate_space"] == "native"
    assert report["strategy_a"]["status"]
    assert report["strategy_b"]["candidate_count"] > 0
    assert "final_estimate" in report
