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
    hsv = to_hsv(image)
    if hue_min <= hue_max:
        hue_mask = (hsv[:, :, 0] >= int(hue_min)) & (hsv[:, :, 0] <= int(hue_max))
    else:
        hue_mask = (hsv[:, :, 0] >= int(hue_min)) | (hsv[:, :, 0] <= int(hue_max))
    mask = hue_mask & (hsv[:, :, 1] >= int(sat_min)) & (hsv[:, :, 2] >= int(val_min))
    return (mask.astype(np.uint8) * 255)


def portal_outer_mask(
    image: np.ndarray,
    *,
    sat_max: int = 115,
    val_min: int = 105,
    blue_mask: np.ndarray | None = None,
) -> np.ndarray:
    hsv = to_hsv(image)
    mask = (hsv[:, :, 1] <= int(sat_max)) & (hsv[:, :, 2] >= int(val_min))
    if blue_mask is not None:
        mask &= blue_mask == 0
    return (mask.astype(np.uint8) * 255)


def resize_image(image: np.ndarray, scale: float) -> np.ndarray:
    h, w = image.shape[:2]
    new_w = max(4, int(round(w * float(scale))))
    new_h = max(4, int(round(h * float(scale))))
    return cv2.resize(to_bgr(image), (new_w, new_h), interpolation=cv2.INTER_AREA)


def resize_mask(mask: np.ndarray, scale: float) -> np.ndarray:
    h, w = mask.shape[:2]
    new_w = max(4, int(round(w * float(scale))))
    new_h = max(4, int(round(h * float(scale))))
    return cv2.resize(mask, (new_w, new_h), interpolation=cv2.INTER_NEAREST)


def to_bgr(image: np.ndarray) -> np.ndarray:
    if image.ndim == 2:
        return cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
    return image[:, :, :3]


def to_hsv(image: np.ndarray) -> np.ndarray:
    return cv2.cvtColor(to_bgr(image), cv2.COLOR_BGR2HSV)
