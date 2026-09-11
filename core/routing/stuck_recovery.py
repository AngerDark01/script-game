"""Independent, clock-injected movement progress tracking and safe escape targets."""
from core.routing.geometry import point_distance, line_is_walkable


class ProgressWatchdog:
    def __init__(self, *, timeout_ms=400, minimum_progress=2.):
        if timeout_ms <= 0 or minimum_progress <= 0:
            raise ValueError('progress thresholds must be positive')
        self.timeout_ms, self.minimum_progress = timeout_ms, minimum_progress
        self.reset()

    def reset(self):
        self._anchor = None
        self._since = None

    def update(self, position, *, now_ms, moving):
        if not moving:
            self.reset()
            return False
        if self._anchor is None or now_ms < self._since or point_distance(position, self._anchor) >= self.minimum_progress:
            self._anchor, self._since = tuple(position), now_ms
            return False
        return now_ms-self._since >= self.timeout_ms


def escape_targets(position, direction, walls, *, distance=8.):
    x, y = position
    dx, dy = direction
    candidates = ((x-dy*distance, y+dx*distance), (x+dy*distance, y-dx*distance),
                  (x-dx*distance, y-dy*distance))
    return tuple(p for p in candidates if point_distance(p, position) > 1
                 and line_is_walkable(walls, position, p, corner_safe=True))
