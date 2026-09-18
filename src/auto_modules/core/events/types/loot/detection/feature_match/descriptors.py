from __future__ import annotations

import cv2
import numpy as np

from ..images import to_bgr
from ..scoring import clamp01


def cosine_score(a: np.ndarray, b: np.ndarray) -> float:
    av = a.astype(np.float32).reshape(-1)
    bv = b.astype(np.float32).reshape(-1)
    denom = float(np.linalg.norm(av) * np.linalg.norm(bv))
    if denom <= 1e-6:
        return 0.0
    return clamp01(float(np.dot(av, bv) / denom))


def distance_from_edges(edges: np.ndarray) -> np.ndarray:
    edge_u8 = (edges > 0).astype(np.uint8) * 255
    inv = cv2.bitwise_not(edge_u8)
    return cv2.distanceTransform(inv, cv2.DIST_L2, 3).astype(np.float32)


def hog_descriptor(gray: np.ndarray, mask: np.ndarray, cells: tuple[int, int] = (2, 2), bins: int = 9) -> np.ndarray:
    gray_f = gray.astype(np.float32)
    gx = cv2.Sobel(gray_f, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(gray_f, cv2.CV_32F, 0, 1, ksize=3)
    magnitude, angle = cv2.cartToPolar(gx, gy, angleInDegrees=True)
    angle = np.mod(angle, 180.0)
    mask_bool = mask > 0
    h, w = gray.shape[:2]
    cell_y, cell_x = cells
    parts: list[np.ndarray] = []
    for cy in range(cell_y):
        y1 = int(round(cy * h / cell_y))
        y2 = int(round((cy + 1) * h / cell_y))
        for cx in range(cell_x):
            x1 = int(round(cx * w / cell_x))
            x2 = int(round((cx + 1) * w / cell_x))
            local_mask = mask_bool[y1:y2, x1:x2]
            if int(np.count_nonzero(local_mask)) <= 0:
                parts.append(np.zeros((bins,), dtype=np.float32))
                continue
            local_angle = angle[y1:y2, x1:x2][local_mask]
            local_mag = magnitude[y1:y2, x1:x2][local_mask]
            hist, _ = np.histogram(local_angle, bins=bins, range=(0.0, 180.0), weights=local_mag)
            parts.append(hist.astype(np.float32))
    vector = np.concatenate(parts).astype(np.float32)
    norm = float(np.linalg.norm(vector))
    return vector / max(1e-6, norm)


def masked_template_score(patch: np.ndarray, image: np.ndarray, mask: np.ndarray, gray_template: np.ndarray) -> float:
    if patch.shape[:2] != image.shape[:2]:
        return 0.0
    mask_bool = mask > 0
    if int(np.count_nonzero(mask_bool)) <= 0:
        return 0.0

    patch_values = to_bgr(patch).astype(np.float32)[mask_bool]
    template_values = image.astype(np.float32)[mask_bool]
    color_score = cosine_score(patch_values, template_values)

    patch_gray = cv2.cvtColor(to_bgr(patch), cv2.COLOR_BGR2GRAY).astype(np.float32)
    patch_gray_values = patch_gray[mask_bool]
    template_gray_values = gray_template.astype(np.float32)[mask_bool]
    patch_gray_values = patch_gray_values - float(np.mean(patch_gray_values))
    template_gray_values = template_gray_values - float(np.mean(template_gray_values))
    gray_score = (cosine_score(patch_gray_values, template_gray_values) + 1.0) / 2.0
    return clamp01(max(float(color_score) * 0.94, float(gray_score)))


def edge_overlap_score(patch: np.ndarray, mask: np.ndarray, edge_mask: np.ndarray) -> float:
    if patch.shape[:2] != mask.shape[:2]:
        return 0.0
    gray = cv2.cvtColor(to_bgr(patch), cv2.COLOR_BGR2GRAY)
    patch_edges = (cv2.Canny(gray, 45, 135) > 0) & (mask > 0)
    template_edges = edge_mask > 0
    if int(np.count_nonzero(patch_edges)) <= 0 or int(np.count_nonzero(template_edges)) <= 0:
        return 0.0
    overlap = float(np.count_nonzero(patch_edges & template_edges))
    denom = float(np.sqrt(np.count_nonzero(patch_edges) * np.count_nonzero(template_edges)))
    return clamp01(overlap / max(1e-6, denom))


def chamfer_similarity(patch: np.ndarray, mask: np.ndarray, edge_mask: np.ndarray, edge_distance: np.ndarray) -> float:
    if patch.shape[:2] != mask.shape[:2] or int(np.count_nonzero(edge_mask)) <= 0:
        return 0.0
    gray = cv2.cvtColor(to_bgr(patch), cv2.COLOR_BGR2GRAY)
    search_mask = cv2.dilate(mask, np.ones((3, 3), np.uint8), iterations=1) > 0
    patch_edges = ((cv2.Canny(gray, 45, 135) > 0) & search_mask).astype(np.uint8)
    if int(np.count_nonzero(patch_edges)) <= 0:
        return 0.0
    patch_distance = distance_from_edges(patch_edges)
    t2p = float(np.mean(patch_distance[edge_mask > 0]))
    p2t = float(np.mean(edge_distance[patch_edges > 0]))
    distance = t2p * 0.65 + p2t * 0.35
    return clamp01(float(np.exp(-distance / 3.2)))
