"""Validation and map-origin conversion around the existing phase estimator."""
from math import hypot, isfinite
import numpy as np
from core.shared.frame_registration import FrameRegistration
from core.vision.phase_displacement import estimate_phase_displacement


def track_scroll(previous, current, *, origin, scale=1.0, min_response=0.4, max_shift=40.0):
    invalid = FrameRegistration(False, source='phase_rejected')
    if (not isfinite(scale) or scale <= 0 or len(origin) != 2
            or not all(isfinite(v) for v in origin)):
        raise ValueError('finite origin and positive scale required')
    if (not isinstance(previous, np.ndarray) or not isinstance(current, np.ndarray)
            or previous.ndim != 2 or current.shape != previous.shape
            or min(current.shape) < 2 or not np.isfinite(current).all()
            or not np.isfinite(previous).all() or np.std(previous) < 1e-6
            or np.std(current) < 1e-6):
        return invalid
    shift, response = estimate_phase_displacement(previous, current)
    if (shift is None or not all(isfinite(v) for v in (*shift, response))
            or response < min_response or hypot(*shift) > max_shift):
        return invalid
    # A static wall moving right on the minimap means the viewport origin moved left.
    return FrameRegistration(True, confidence=min(1., max(0., response)),
        frame_origin_global=(origin[0] - scale * shift[0], origin[1] - scale * shift[1]),
        draw_scale=scale, source='phase', frame_size=(current.shape[1], current.shape[0]))
