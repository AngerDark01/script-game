import numpy as np

from auto_modules.core.localization.frame_displacement import FrameDisplacement
from auto_modules.features.poe2.live_terrain.experimental.hybrid_localization.models import HybridFrame
from auto_modules.features.poe2.live_terrain.experimental.multiframe_localization.models import MultiFrameEvidence
from auto_modules.features.poe2.live_terrain.experimental.multiframe_localization.rolling_submap import RollingSubmap


def _item(frame_id, offset):
    mask = np.zeros((4, 4), dtype=np.uint8)
    mask[1, 1:3] = 255
    frame = HybridFrame(frame_id, frame_id * 100, mask, (2.0, 2.0))
    motion = FrameDisplacement((1.0, 0.0), 0.9, 1.0, True, "accepted")
    return MultiFrameEvidence(frame, motion, offset, True, 0)


def test_rebuild_merges_masks_and_keeps_unknown_zero():
    snapshot = RollingSubmap(max_width=16, max_height=16).rebuild([_item(1, (0, 0)), _item(2, (3, 0))])
    assert snapshot.wall_mask.shape == (4, 7)
    assert snapshot.wall_mask[1, 1] == 255
    assert snapshot.wall_mask[1, 4] == 255
    assert snapshot.observed_mask[0, 0] == 255
    assert snapshot.frame_ids == (1, 2)
    assert snapshot.wall_weight.dtype == np.float32
    assert snapshot.observed_weight.dtype == np.float32
    assert snapshot.last_frame_id[0, 0] == 1


def test_rebuild_from_retained_frames_removes_evicted_contribution():
    submap = RollingSubmap()
    submap.rebuild([_item(1, (0, 0)), _item(2, (3, 0))])
    snapshot = submap.rebuild([_item(2, (3, 0))])
    assert snapshot.frame_ids == (2,)
    assert snapshot.wall_mask.shape == (4, 4)


def test_bounded_submap_keeps_the_latest_view_when_span_exceeds_budget():
    snapshot = RollingSubmap(max_width=16, max_height=16).rebuild([
        _item(1, (0, 0)),
        _item(2, (100, 0)),
    ])
    assert snapshot.origin[0] > 0
    assert snapshot.frame_ids == (1, 2)
    assert np.count_nonzero(snapshot.wall_mask) > 0


def test_weighted_rebuild_does_not_let_one_low_quality_wall_override_clear_evidence():
    wall = _item(1, (0, 0))
    clear_frame = HybridFrame(2, 200, np.zeros((4, 4), dtype=np.uint8), (2.0, 2.0))
    clear = MultiFrameEvidence(
        clear_frame,
        FrameDisplacement((1.0, 0.0), 0.9, 1.0, True, "accepted"),
        (0.0, 0.0),
        True,
        0,
    )
    low_quality_wall = MultiFrameEvidence(
        wall.frame,
        FrameDisplacement((1.0, 0.0), 0.1, 1.0, True, "accepted"),
        wall.local_offset,
        True,
        0,
    )

    snapshot = RollingSubmap(max_frame_weight=1.0).rebuild((low_quality_wall, clear))

    assert snapshot.wall_mask[1, 1] == 0
    assert snapshot.observed_weight[1, 1] > snapshot.wall_weight[1, 1]
