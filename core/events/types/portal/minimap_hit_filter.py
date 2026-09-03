from __future__ import annotations

import cv2
import numpy as np


def portal_color_check(frame, hit, min_blue_ratio: float) -> dict:
    """Check whether a portal minimap hit contains enough blue pixels."""
    x, y = hit.top_left
    w, h = hit.size
    pad = max(2, int(round(min(w, h) * 0.15)))
    left = max(0, int(x) - pad)
    top = max(0, int(y) - pad)
    right = min(frame.shape[1], int(x + w) + pad)
    bottom = min(frame.shape[0], int(y + h) + pad)
    patch = frame[top:bottom, left:right]
    if patch.size == 0:
        return {"accepted": False, "blue_ratio": 0.0, "blue_pixels": 0}

    if patch.ndim == 3:
        hsv = cv2.cvtColor(patch, cv2.COLOR_BGR2HSV)
    else:
        hsv = cv2.cvtColor(cv2.cvtColor(patch, cv2.COLOR_GRAY2BGR), cv2.COLOR_BGR2HSV)

    blue_mask = (
        (hsv[:, :, 0] >= 82)
        & (hsv[:, :, 0] <= 136)
        & (hsv[:, :, 1] >= 35)
        & (hsv[:, :, 2] >= 70)
    )
    blue_pixels = int(np.count_nonzero(blue_mask))
    area = int(patch.shape[0] * patch.shape[1])
    blue_ratio = float(blue_pixels / max(1, area))
    return {
        "accepted": bool(blue_ratio >= float(min_blue_ratio) and blue_pixels >= 18),
        "blue_ratio": blue_ratio,
        "blue_pixels": blue_pixels,
    }
