"""Bounded translation registration using cached wall-distance correlation.

This first implementation evaluates all translations inside the explicit bound
in OpenCV (no Python candidate loop). Pyramid/ORB strategies remain optional;
this class never silently searches the whole map.
"""
from math import ceil, floor, isfinite
from time import perf_counter
import cv2
import numpy as np
from core.localization.frame_matcher import scale_wall_template
from core.shared.frame_registration import FrameRegistration


class LocalMapMatcher:
    def __init__(self, runtime, *, max_error=1.5, min_margin=0.15, min_features=12):
        if max_error <= 0 or min_margin < 0 or min_features < 1:
            raise ValueError('invalid matching thresholds')
        self.runtime = runtime
        self.max_error, self.min_margin, self.min_features = max_error, min_margin, min_features

    def match(self, walls, *, origin, radius, scale=1.0):
        started = perf_counter()
        if (not isfinite(radius) or radius < 0 or not isfinite(scale) or scale <= 0
                or len(origin) != 2 or not all(isfinite(v) for v in origin)):
            raise ValueError('invalid search geometry')
        invalid = FrameRegistration(False, source='bounded_match_rejected')
        if (walls.ndim != 2 or walls.size == 0 or not np.isfinite(walls).all()
                or min(walls.shape) * scale < 1):
            return invalid
        template = (scale_wall_template(walls, scale, 1) > 0).astype(np.float32)
        count = int(template.sum())
        if count < self.min_features or not np.isfinite(self.runtime.distance_field).all():
            return invalid
        h, w = template.shape
        mh, mw = self.runtime.shape
        x0, y0 = max(0, ceil(origin[0]-radius)), max(0, ceil(origin[1]-radius))
        x1, y1 = min(mw-w, floor(origin[0]+radius)), min(mh-h, floor(origin[1]+radius))
        if x1 < x0 or y1 < y0:
            return invalid
        field = self.runtime.distance_field[y0:y1+h, x0:x1+w]
        costs = np.maximum(0., cv2.matchTemplate(field, template, cv2.TM_CCORR) / count)
        by, bx = np.unravel_index(np.argmin(costs), costs.shape)
        error = float(costs[by, bx])
        # Exclude the same peak's subpixel neighbourhood before testing ambiguity.
        other = costs.copy()
        other[max(0, by-2):by+3, max(0, bx-2):bx+3] = np.inf
        margin = float(other.min()) - error
        valid = error <= self.max_error and margin >= self.min_margin
        return FrameRegistration(valid,
            confidence=max(0., 1.-error/self.max_error) if valid else 0.,
            frame_origin_global=(float(x0+bx), float(y0+by)) if valid else None,
            draw_scale=scale, source='local_chamfer', frame_size=(walls.shape[1], walls.shape[0]),
            metadata={'mean_wall_error_px': error, 'candidate_margin': margin,
                      'search_origins': (x0, y0, x1, y1),
                      'elapsed_ms': (perf_counter()-started)*1000})
