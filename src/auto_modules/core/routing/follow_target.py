"""Generate follow targets from observed leader history, without device I/O."""
from collections import deque
from math import isfinite
from auto_modules.core.routing.geometry import build_cumulative_lengths, interpolate_by_distance, point_distance


class FollowTargetGenerator:
    def __init__(self, max_samples=256):
        if max_samples < 2:
            raise ValueError('max_samples must be at least two')
        self._points = deque(maxlen=max_samples)
        self._last_ms = -1

    def observe(self, position, captured_at_ms):
        if not all(isfinite(v) for v in (*position, captured_at_ms)) or len(position) != 2:
            raise ValueError('finite position/time required')
        if captured_at_ms <= self._last_ms:
            return False
        self._last_ms = captured_at_ms
        if not self._points or point_distance(self._points[-1], position) > .5:
            self._points.append(tuple(position))
        return True

    def target(self, lag_distance):
        if not isfinite(lag_distance) or lag_distance < 0:
            raise ValueError('lag_distance must be finite and non-negative')
        path = list(self._points)
        if not path:
            return None
        cumulative = build_cumulative_lengths(path)
        return interpolate_by_distance(path, cumulative, max(0., cumulative[-1]-lag_distance))

    def reset(self):
        self._points.clear()
        self._last_ms = -1
