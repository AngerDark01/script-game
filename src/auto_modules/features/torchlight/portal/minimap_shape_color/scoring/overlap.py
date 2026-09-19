from __future__ import annotations

import numpy as np


def f1_score(patch_mask: np.ndarray, template_mask: np.ndarray) -> tuple[float, int, int]:
    if patch_mask.shape[:2] != template_mask.shape[:2]:
        return 0.0, 0, int(np.count_nonzero(template_mask))
    patch = patch_mask > 0
    template = template_mask > 0
    patch_pixels = int(np.count_nonzero(patch))
    template_pixels = int(np.count_nonzero(template))
    if patch_pixels <= 0 or template_pixels <= 0:
        return 0.0, patch_pixels, template_pixels
    intersection = int(np.count_nonzero(patch & template))
    precision = float(intersection) / float(max(1, patch_pixels))
    recall = float(intersection) / float(max(1, template_pixels))
    if precision + recall <= 0:
        return 0.0, patch_pixels, template_pixels
    return float(2.0 * precision * recall / (precision + recall)), patch_pixels, template_pixels
