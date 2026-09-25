import json

import numpy as np
import pytest

from auto_modules.core.localization.frame_displacement import FrameDisplacement
from auto_modules.features.poe2.live_terrain.experimental.hybrid_localization.models import HybridFrame, PositionAnchor
from auto_modules.features.poe2.live_terrain.experimental.multiframe_localization.archive import MultiframeArchive
from auto_modules.features.poe2.live_terrain.experimental.hybrid_localization.models import SimilarityTransform2D
from auto_modules.features.poe2.live_terrain.experimental.multiframe_localization.models import CandidateRegion, MultiFrameEvidence, PositionEstimate
from auto_modules.features.poe2.live_terrain.terrain_reference import TerrainReference


def test_archive_writes_manifest_and_compressed_masks(tmp_path):
    frame = HybridFrame(1, 100, np.eye(4, dtype=np.uint8), (2, 2))
    evidence = MultiFrameEvidence(frame, FrameDisplacement((1, 0), .9, 1, True, "accepted"), (0, 0), True, 0, raw_frame=np.zeros((4, 4, 3), dtype=np.uint8))
    anchor = PositionAnchor((10, 11), "Map:A", 90, "memory")
    reference = TerrainReference(
        np.ones((4, 4), dtype=bool),
        np.eye(4, dtype=np.uint8) * 255,
        np.full((4, 4), 255, dtype=np.uint8),
        4,
        4,
        {"instance_id": "Map:A"},
    )
    target = MultiframeArchive().save(
        tmp_path / "run",
        evidence=(evidence,),
        anchor=anchor,
        instance_id="Map:A",
        reference=reference,
        diagnostics={"read_count": 1},
    )
    manifest = json.loads((target / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["frame_ids"] == [1]
    assert manifest["diagnostics"]["read_count"] == 1
    assert manifest["schema_version"] == 3
    assert manifest["coordinate_space"] == "native"
    assert manifest["anchor"]["position"] == [10.0, 11.0]
    assert manifest["frames"][0]["observed_key"] == "observed_1"
    assert manifest["frames"][0]["raw_key"] == "raw_1"
    assert (target / "evidence.npz").exists()
    assert not list(tmp_path.glob(".run.tmp-*"))

    bundle = MultiframeArchive().load(target)
    assert bundle.instance_id == "Map:A"
    assert bundle.anchor == anchor
    assert bundle.reference.metadata["instance_id"] == "Map:A"
    assert np.array_equal(bundle.reference.wall_layer, reference.wall_layer)
    assert len(bundle.evidence) == 1
    assert np.array_equal(bundle.evidence[0].frame.wall_mask, evidence.frame.wall_mask)
    assert np.array_equal(bundle.evidence[0].observed_mask, evidence.observed_mask)
    assert bundle.evidence[0].motion == evidence.motion


def test_archive_round_trips_position_estimate_and_candidate_regions(tmp_path):
    frame = HybridFrame(1, 100, np.eye(4, dtype=np.uint8), (2, 2))
    evidence = MultiFrameEvidence(frame, FrameDisplacement((1, 0), .9, 1, True, "accepted"), (0, 0), True, 0)
    anchor = PositionAnchor((10, 11), "Map:A", 90, "memory")
    reference = TerrainReference(
        np.ones((4, 4), dtype=bool),
        np.eye(4, dtype=np.uint8) * 255,
        np.full((4, 4), 255, dtype=np.uint8),
        4,
        4,
        {"instance_id": "Map:A"},
    )
    estimate = PositionEstimate(
        "confirmed",
        (10.0, 11.0),
        (1.0, 2.0),
        np.eye(2),
        (
            CandidateRegion(
                SimilarityTransform2D(45.0, False, 1.0, (3.0, 4.0)),
                (10.0, 11.0),
                np.eye(2),
                0.9,
                (1,),
            ),
        ),
        "Map:A",
        2,
        3,
        True,
        20,
        "visual_f2f",
        "ok",
        {"captured_at_ms": 120},
    )
    target = MultiframeArchive().save(
        tmp_path / "run",
        evidence=(evidence,),
        anchor=anchor,
        instance_id="Map:A",
        reference=reference,
        estimate=estimate,
    )

    loaded = MultiframeArchive().load(target)

    assert loaded.estimate is not None
    assert loaded.estimate.position == estimate.position
    assert loaded.estimate.velocity == estimate.velocity
    assert np.array_equal(loaded.estimate.covariance, estimate.covariance)
    assert loaded.estimate.candidate_regions[0].transform.angle_degrees == 45.0
    assert loaded.estimate.candidate_regions[0].support_frames == (1,)


def test_archive_rejects_empty_evidence(tmp_path):
    anchor = PositionAnchor((10, 11), "Map:A", 90, "memory")
    reference = TerrainReference(
        np.ones((4, 4), dtype=bool),
        np.eye(4, dtype=np.uint8) * 255,
        np.full((4, 4), 255, dtype=np.uint8),
        4,
        4,
        {"instance_id": "Map:A"},
    )
    with pytest.raises(ValueError, match="empty evidence"):
        MultiframeArchive().save(
            tmp_path / "empty",
            evidence=(),
            anchor=anchor,
            instance_id="Map:A",
            reference=reference,
        )


def test_archive_rejects_old_manual_orientation_schema(tmp_path):
    target = tmp_path / "old"
    target.mkdir()
    (target / "manifest.json").write_text(
        json.dumps({"schema_version": 2, "coordinate_space": "oriented-preview"}),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="unsupported multiframe archive schema"):
        MultiframeArchive().load(target)


def test_archive_rejects_malformed_motion_shift(tmp_path):
    frame = HybridFrame(1, 100, np.eye(4, dtype=np.uint8), (2, 2))
    evidence = MultiFrameEvidence(
        frame,
        FrameDisplacement((1, 0), .9, 1, True, "accepted"),
        (0, 0),
        True,
        0,
    )
    anchor = PositionAnchor((10, 11), "Map:A", 90, "memory")
    reference = TerrainReference(
        np.ones((4, 4), dtype=bool),
        np.eye(4, dtype=np.uint8) * 255,
        np.full((4, 4), 255, dtype=np.uint8),
        4,
        4,
        {"instance_id": "Map:A"},
    )
    target = MultiframeArchive().save(
        tmp_path / "run",
        evidence=(evidence,),
        anchor=anchor,
        instance_id="Map:A",
        reference=reference,
    )
    manifest_path = target / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["frames"][0]["motion"]["shift"] = [1.0]
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(ValueError, match="motion shift must contain two values"):
        MultiframeArchive().load(target)
