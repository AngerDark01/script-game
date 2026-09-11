import numpy as np
from core.perception.models import FrameContext, CoordinateSpace, TargetDetection
from core.localization.local_matcher import LocalMapMatcher
from core.localization.map_runtime import MapRuntime
from core.localization.dual_localizer import MultiMarkerLocalizer


class Marks:
    def detect(self, frame):
        return {'A1': TargetDetection('player', (5, 6), CoordinateSpace.MINIMAP, .9),
                'A2': None}


def make_localizer():
    walls = np.zeros((100, 120), np.uint8)
    walls[30:46, 40] = 255
    walls[45, 40:55] = 255
    walls[32:40, 51] = 255
    return MultiMarkerLocalizer(LocalMapMatcher(MapRuntime.from_wall_layer(walls)),
        Marks(), initial_origin=(35, 25), search_radius=12), walls[25:50, 35:60]


def test_shared_registration_missing_marker_is_independent():
    localizer, walls = make_localizer()
    frame = FrameContext(walls, captured_at_ms=100, coordinate_space=CoordinateSpace.MINIMAP)
    result = localizer.update(frame, walls, now_ms=100)
    assert result.positions['A1'].position == (40, 31)
    assert result.positions['A2'].position is None
    assert result.captured_at_ms == 100
    assert not localizer.update(frame, walls, now_ms=101).registration.valid


def test_stale_or_wrong_frame_masks_never_return_live_position():
    localizer, walls = make_localizer()
    frame = FrameContext(walls, captured_at_ms=100, coordinate_space=CoordinateSpace.MINIMAP)
    assert not localizer.update(frame, walls, now_ms=1000).registration.valid
    assert not localizer.update(frame, walls[:10], now_ms=100).registration.valid
