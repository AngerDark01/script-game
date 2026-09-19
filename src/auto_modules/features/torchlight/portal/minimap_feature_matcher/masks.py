from __future__ import annotations

import cv2
import numpy as np


def portal_blue_mask(
    image: np.ndarray,
    *,
    hue_min: int = 82,
    hue_max: int = 136,
    sat_min: int = 55,
    val_min: int = 95,
) -> np.ndarray:
    if image.ndim == 2:
        bgr = cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
    else:
        bgr = image[:, :, :3]
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
    if hue_min <= hue_max:
        hue_mask = (hsv[:, :, 0] >= int(hue_min)) & (hsv[:, :, 0] <= int(hue_max))
    else:
        hue_mask = (hsv[:, :, 0] >= int(hue_min)) | (hsv[:, :, 0] <= int(hue_max))
    mask = (
        hue_mask
        & (hsv[:, :, 1] >= int(sat_min))
        & (hsv[:, :, 2] >= int(val_min))
    )
    return (mask.astype(np.uint8) * 255)
