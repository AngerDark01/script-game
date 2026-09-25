import numpy as np

from auto_modules.core.localization.frame_displacement import FrameDisplacement
from auto_modules.features.poe2.live_terrain.experimental.hybrid_localization.models import HybridFrame, SimilarityTransform2D, PositionAnchor
from auto_modules.features.poe2.live_terrain.experimental.multiframe_localization.models import MultiFrameEvidence
from auto_modules.features.poe2.live_terrain.experimental.multiframe_localization.shape_registration import transform_points
from auto_modules.features.poe2.live_terrain.experimental.multiframe_localization.strategy_b import CandidateHypothesis, JointCandidateStrategy, deduplicate_candidates


def test_dedup_keeps_different_reflections_and_angles():
    first = CandidateHypothesis(SimilarityTransform2D(0, False, 1, (1, 1)), (1, 1), 1, .5, (1,))
    duplicate = CandidateHypothesis(SimilarityTransform2D(.2, False, 1.001, (1.5, 1.5)), (1.5, 1.5), 2, .4, (1,))
    reflected = CandidateHypothesis(SimilarityTransform2D(0, True, 1, (1, 1)), (1, 1), 3, .3, (1,))
    assert len(deduplicate_candidates([first, duplicate, reflected])) == 2


def test_empty_strategy_is_not_confirmable():
    strategy = JointCandidateStrategy()
    result = strategy.seed([], evidence_version=1)
    assert not strategy.confirmable(result)
    strategy.reset()
    assert strategy.seed([], evidence_version=2).evidence_version == 2


def test_strategy_b_refines_non_45_degree_rotation():
    wall = np.zeros((24, 24), dtype=np.uint8)
    wall[4:20, 5] = 255
    wall[18, 5:17] = 255
    local_player = (12.0, 12.0)
    anchor = PositionAnchor((60.0, 55.0), "Map:A", 100, "memory")
    basis = SimilarityTransform2D(31.0, False, 1.0, (0.0, 0.0))
    mapped_player = transform_points(np.array([local_player]), basis)[0]
    truth = SimilarityTransform2D(
        31.0,
        False,
        1.0,
        (anchor.position[0] - mapped_player[0], anchor.position[1] - mapped_player[1]),
    )
    points = np.column_stack(np.nonzero(wall))[:, ::-1]
    projected = np.rint(transform_points(points, truth)).astype(int)
    reference = np.zeros((120, 120), dtype=np.uint8)
    reference[projected[:, 1], projected[:, 0]] = 255
    frame = HybridFrame(1, 100, wall, local_player)
    evidence = MultiFrameEvidence(
        frame,
        FrameDisplacement((1.0, 0.0), 0.9, 1.0, True, "accepted"),
        (0.0, 0.0),
        True,
        0,
    )

    result = JointCandidateStrategy(max_candidates=6).update(
        (evidence,),
        anchor=anchor,
        reference_boundary=reference,
        evidence_version=1,
    )

    assert result.best is not None
    delta = abs((result.best.transform.angle_degrees - 31.0 + 180.0) % 360.0 - 180.0)
    assert delta <= 1.5
    assert result.best.refinement_level == "fine"


def test_strategy_b_returns_absolute_transform_after_reference_crop():
    wall = np.zeros((24, 24), dtype=np.uint8)
    wall[4:20, 5] = 255
    wall[18, 5:17] = 255
    local_player = (12.0, 12.0)
    origin = (10.0, 20.0)
    anchor = PositionAnchor((60.0, 55.0), "Map:A", 100, "memory")
    truth = SimilarityTransform2D(
        31.0,
        False,
        1.0,
        (anchor.position[0] - transform_points(np.array([local_player]), SimilarityTransform2D(31.0, False, 1.0, (0.0, 0.0)))[0][0],
         anchor.position[1] - transform_points(np.array([local_player]), SimilarityTransform2D(31.0, False, 1.0, (0.0, 0.0)))[0][1]),
    )
    points = np.column_stack(np.nonzero(wall))[:, ::-1]
    reference = np.zeros((120, 120), dtype=np.uint8)
    projected = np.rint(transform_points(points, truth)).astype(int)
    reference[projected[:, 1], projected[:, 0]] = 255
    frame = HybridFrame(1, 100, wall, local_player)
    evidence = MultiFrameEvidence(
        frame,
        FrameDisplacement((1.0, 0.0), 0.9, 1.0, True, "accepted"),
        (0.0, 0.0),
        True,
        0,
    )

    crop = reference[int(origin[1]):, int(origin[0]):]
    strategy = JointCandidateStrategy(max_candidates=6)
    result = strategy.update(
        (evidence,),
        anchor=anchor,
        reference_boundary=crop,
        reference_origin=origin,
        evidence_version=1,
    )

    assert result.best is not None
    assert strategy._candidates
    assert np.allclose(
        np.asarray(result.best.transform.translation),
        np.asarray(strategy._candidates[0].transform.translation) + np.asarray(origin),
    )
