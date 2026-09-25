from types import SimpleNamespace

import numpy as np

from auto_modules.core.localization.frame_displacement import FrameDisplacement
from auto_modules.features.poe2.live_terrain.experimental.hybrid_localization.models import HybridFrame, PositionAnchor
from auto_modules.features.poe2.live_terrain.experimental.multiframe_localization.evidence_window import EvidenceWindow
from auto_modules.features.poe2.live_terrain.experimental.multiframe_localization.models import MultiFrameEvidence
from auto_modules.features.poe2.live_terrain.experimental.multiframe_localization.rolling_submap import RollingSubmap
from auto_modules.features.poe2.live_terrain.experimental.multiframe_localization.strategy_a import StitchThenRegister, SubmapThresholds


def _item(frame_id, offset):
    mask = np.zeros((8, 8), dtype=np.uint8)
    mask[2:6, 2] = 255
    frame = HybridFrame(frame_id, frame_id * 100, mask, (4.0, 4.0))
    return MultiFrameEvidence(frame, FrameDisplacement((3, 0), .9, 3, True, "accepted"), offset, True, 0)


def test_strategy_a_waits_until_structure_and_attempts_once_per_version():
    window = EvidenceWindow(max_keyframes=8)
    window.append(_item(1, (0, 0)))
    submap = RollingSubmap()
    registrar = SimpleNamespace(register_submap=lambda snapshot, **kwargs: "candidate")
    strategy = StitchThenRegister(registrar, thresholds=SubmapThresholds(min_frames=2, min_wall_pixels=4, min_span=2), require_holdout=False)
    anchor = PositionAnchor((10, 10), "Map:A", 100, "memory")
    assert strategy.evaluate(window, submap, anchor=anchor, reference=object()).status == "insufficient_evidence"
    window.append(_item(2, (3, 0)))
    result = strategy.evaluate(window, submap, anchor=anchor, reference=object())
    assert result.status == "confirmed"
    assert strategy.evaluate(window, submap, anchor=anchor, reference=object()).reason == "evidence_version_already_attempted"
    strategy.reset()
    assert strategy.evaluate(window, submap, anchor=anchor, reference=object()).status == "confirmed"
