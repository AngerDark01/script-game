from __future__ import annotations

import cv2
import numpy as np

from ..models import PreparedShapeColorTemplate
from .color import color_response_map


def combined_shape_color_response(
    frame: np.ndarray,
    frame_blue: np.ndarray,
    frame_outer: np.ndarray,
    frame_shape: np.ndarray,
    frame_edges: np.ndarray,
    prepared: PreparedShapeColorTemplate,
) -> np.ndarray:
    blue_response = mask_response(frame_blue, prepared.blue_mask)
    outer_response = mask_response(frame_outer, prepared.outer_mask)
    shape_response = mask_response(frame_shape, prepared.shape_mask)
    edge_response = mask_response(frame_edges, prepared.edge_mask)
    color_response = color_response_map(frame, prepared.image, prepared.shape_mask)
    return (
        blue_response * 0.30
        + outer_response * 0.24
        + shape_response * 0.24
        + edge_response * 0.12
        + color_response * 0.10
    )


def mask_response(frame_mask: np.ndarray, template_mask: np.ndarray) -> np.ndarray:
    if int(np.count_nonzero(template_mask)) < 3:
        out_h = frame_mask.shape[0] - template_mask.shape[0] + 1
        out_w = frame_mask.shape[1] - template_mask.shape[1] + 1
        return np.zeros((max(1, out_h), max(1, out_w)), dtype=np.float32)
    frame_norm = frame_mask.astype(np.float32) / 255.0
    template_norm = template_mask.astype(np.float32) / 255.0
    response = cv2.matchTemplate(frame_norm, template_norm, cv2.TM_CCORR_NORMED)
    return np.nan_to_num(response, nan=-1.0, posinf=-1.0, neginf=-1.0)


def response_hits(response: np.ndarray, limit: int, threshold: float, suppress_radius: int):
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
