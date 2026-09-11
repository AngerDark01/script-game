import numpy as np
import pytest
from core.perception.models import FrameContext, CoordinateSpace
from core.localization.minimap_frames import crop_minimap, LatestFrame


def test_crop_keeps_capture_time_and_source_geometry():
    frame = FrameContext(np.zeros((20, 30, 3), np.uint8), captured_at_ms=123, source='test')
    result = crop_minimap(frame, left=3, top=4, width=10, height=12)
    assert result.image.shape == (12, 10, 3)
    assert result.captured_at_ms == 123
    assert result.coordinate_space == CoordinateSpace.MINIMAP
    assert result.metadata['source_geometry'].map_point_to_source((0, 0)) == (3, 4)
    with pytest.raises(ValueError):
        crop_minimap(frame, left=-1, top=0, width=5, height=5)


def test_latest_frame_rejects_late_and_duplicate_samples():
    latest = LatestFrame()
    def frame(t):
        return FrameContext(np.zeros((3, 3), np.uint8), captured_at_ms=t)
    assert latest.publish(frame(20))
    assert not latest.publish(frame(19))
    assert not latest.publish(frame(20))
    assert latest.read().captured_at_ms == 20
    latest.clear()
    assert latest.read() is None
