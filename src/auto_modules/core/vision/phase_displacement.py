from __future__ import annotations

import cv2
import numpy as np


def estimate_phase_displacement(img1, img2, *, dead_zone: float = 0.2):
    """Estimate image displacement with phase correlation.

    Returns the raw OpenCV shift and response, except tiny shifts inside the
    dead zone are normalized to ``(0.0, 0.0)``. On invalid inputs or OpenCV
    errors, returns ``(None, 0.0)`` to match existing caller behavior.
    """
    try:
        h, w = img1.shape
        hann = cv2.createHanningWindow((w, h), cv2.CV_32F)
        shift, response = cv2.phaseCorrelate(
            img1.astype(np.float32),
            img2.astype(np.float32),
            window=hann,
        )

        dist = np.sqrt(shift[0] ** 2 + shift[1] ** 2)
        if dist < float(dead_zone):
            return (0.0, 0.0), response

        return shift, response
    except Exception:
        return None, 0.0
