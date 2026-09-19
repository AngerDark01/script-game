from __future__ import annotations

import cv2
import numpy as np


def _resize_mask(mask: np.ndarray, scale: float) -> np.ndarray:
    h, w = mask.shape[:2]
    new_w = max(4, int(round(w * float(scale))))
    new_h = max(4, int(round(h * float(scale))))
    return cv2.resize(mask, (new_w, new_h), interpolation=cv2.INTER_NEAREST)


def _response_hits(response: np.ndarray, limit: int, threshold: float, suppress_radius: int):
    hits = []
    work = response.copy()
    for _ in range(max(1, int(limit))):
        _, max_val, _, max_loc = cv2.minMaxLoc(work)
        if float(max_val) < float(threshold):
            break
        hits.append((float(max_val), max_loc))
        x, y = max_loc
        x1 = max(0, x - int(suppress_radius))
        y1 = max(0, y - int(suppress_radius))
        x2 = min(work.shape[1], x + int(suppress_radius) + 1)
        y2 = min(work.shape[0], y + int(suppress_radius) + 1)
        work[y1:y2, x1:x2] = -1.0
    return hits
