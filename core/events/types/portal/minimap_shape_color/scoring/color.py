from __future__ import annotations

import cv2
import numpy as np

from ..masks import to_bgr, to_hsv


def color_response_map(frame: np.ndarray, template: np.ndarray, shape_mask: np.ndarray) -> np.ndarray:
    try:
        if int(np.count_nonzero(shape_mask)) >= 8:
            response = cv2.matchTemplate(to_bgr(frame), template, cv2.TM_CCORR_NORMED, mask=shape_mask)
        else:
            response = cv2.matchTemplate(to_bgr(frame), template, cv2.TM_CCOEFF_NORMED)
        return np.nan_to_num(response, nan=-1.0, posinf=-1.0, neginf=-1.0)
    except cv2.error:
        out_h = frame.shape[0] - template.shape[0] + 1
        out_w = frame.shape[1] - template.shape[1] + 1
        return np.zeros((max(1, out_h), max(1, out_w)), dtype=np.float32)


def patch_color_score(frame_patch: np.ndarray, template: np.ndarray, shape_mask: np.ndarray) -> float:
    if frame_patch.shape[:2] != template.shape[:2] or frame_patch.size == 0:
        return 0.0
    mask = shape_mask > 0
    if int(np.count_nonzero(mask)) < 3:
        return 0.0
    patch_hsv = to_hsv(frame_patch).astype(np.float32)
    template_hsv = to_hsv(template).astype(np.float32)
    diff = np.abs(patch_hsv[mask] - template_hsv[mask])
    hue_diff = np.minimum(diff[:, 0], 180.0 - diff[:, 0]) / 90.0
    sat_diff = diff[:, 1] / 255.0
    val_diff = diff[:, 2] / 255.0
    distance = hue_diff * 0.45 + sat_diff * 0.25 + val_diff * 0.30
    return float(max(0.0, 1.0 - float(np.mean(distance))))
