"""Compose shared map registration and independent observations, no device I/O."""
from dataclasses import dataclass
from math import isfinite
from core.perception.models import CoordinateSpace
from core.shared.frame_registration import FrameRegistration
from core.localization.result import LocalizationResult
from core.localization.phase_tracker import track_scroll
from core.spatial.calibration import AffineTransform
from core.spatial.models import Point2D


@dataclass(frozen=True)
class LocalizationSnapshot:
    captured_at_ms: int | None
    registration: FrameRegistration
    positions: dict[str, LocalizationResult]


class MultiMarkerLocalizer:
    """A single-player and dual-player pipeline using identical underlying APIs.

    All observations and registration MUST come from the same captured frame.
    Phase prediction is always checked against the map to prevent accumulated
    drift. No unbounded/global search or stale-transform fallback is performed.
    """
    def __init__(self, matcher, markers, *, initial_origin, search_radius=100, scale=1., ttl_ms=250):
        if (len(initial_origin) != 2 or not all(isfinite(v) for v in initial_origin)
                or not isfinite(scale) or scale <= 0 or search_radius < 0 or ttl_ms <= 0):
            raise ValueError('invalid localization configuration')
        self.matcher, self.markers = matcher, markers
        self.origin = tuple(initial_origin)
        self.search_radius, self.scale, self.ttl_ms = search_radius, scale, ttl_ms
        self._previous = None
        self._last_time = -1

    def update(self, frame, wall_mask, *, now_ms):
        stamp = frame.captured_at_ms
        invalid = FrameRegistration(False, source='invalid_or_stale_frame')
        if (stamp is None or stamp <= self._last_time or not 0 <= now_ms-stamp <= self.ttl_ms
                or frame.coordinate_space != CoordinateSpace.MINIMAP
                or wall_mask.shape != frame.image.shape[:2]):
            return LocalizationSnapshot(stamp, invalid, {})
        self._last_time = stamp
        registration = invalid
        if self._previous is not None:
            predicted = track_scroll(self._previous, wall_mask, origin=self.origin, scale=self.scale)
            if predicted.valid:
                registration = self.matcher.match(wall_mask, origin=predicted.frame_origin_global,
                                                  radius=2, scale=self.scale)
        if not registration.valid:
            registration = self.matcher.match(wall_mask, origin=self.origin,
                                              radius=self.search_radius, scale=self.scale)
        if not registration.valid:
            self._previous = None
            return LocalizationSnapshot(stamp, registration, {})
        self.origin = registration.frame_origin_global
        self._previous = wall_mask.copy()
        transform = AffineTransform(self.scale, 0, self.origin[0], 0, self.scale, self.origin[1])
        positions = {}
        for identity, observation in self.markers.detect(frame).items():
            position = None
            confidence = 0.
            if observation is not None:
                x, y = observation.center
                h, w = wall_mask.shape
                if isfinite(x) and isfinite(y) and 0 <= x < w and 0 <= y < h:
                    mapped = transform.map_point(Point2D(x, y))
                    position = (mapped.x, mapped.y)
                    confidence = min(registration.confidence, observation.confidence)
            positions[identity] = LocalizationResult(position, confidence,
                registration_valid=registration.valid, source='marker_map_registration',
                metadata={'captured_at_ms': stamp, 'identity': identity})
        return LocalizationSnapshot(stamp, registration, positions)
