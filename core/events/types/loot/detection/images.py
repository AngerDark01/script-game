from __future__ import annotations

import cv2
import numpy as np


def to_bgr(image: np.ndarray) -> np.ndarray:
    if image.ndim == 2:
        return cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
    if image.shape[2] == 4:
        return image[:, :, :3]
    return image[:, :, :3]


def alpha_foreground_mask(image: np.ndarray) -> np.ndarray | None:
    if image.ndim != 3 or image.shape[2] < 4:
        return None
    alpha = image[:, :, 3]
    if int(np.count_nonzero(alpha)) <= 0:
        return None
    mask = (alpha > 0).astype(np.uint8) * 255
    return cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((2, 2), np.uint8))


def foreground_mask(image: np.ndarray) -> np.ndarray:
    alpha_mask = alpha_foreground_mask(image)
    if alpha_mask is not None:
        return alpha_mask

    return icon_foreground_mask(image)


def icon_foreground_mask(image: np.ndarray) -> np.ndarray:
    bgr = to_bgr(image)
    if bgr.size == 0:
        return np.zeros(bgr.shape[:2], dtype=np.uint8)

    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
    h = hsv[:, :, 0]
    s = hsv[:, :, 1]
    v = hsv[:, :, 2]

    blue_background = (h >= 75) & (h <= 145) & (s >= 28)
    gold = (h >= 12) & (h <= 58) & (((s >= 80) & (v >= 75)) | ((s >= 45) & (v >= 115)))
    red = ((h <= 18) | (h >= 165)) & (s >= 45) & (v >= 95)
    silver = (s <= 72) & (v >= 128)
    bright = (v >= 174) & ~blue_background
    gray_body = (s <= 90) & (v >= 76) & ~blue_background
    open_kernel = np.ones((2, 2), np.uint8)
    warm_mask = (gold | red).astype(np.uint8) * 255
    warm_mask = cv2.morphologyEx(warm_mask, cv2.MORPH_OPEN, open_kernel)

    cool_mask = (silver | bright | gray_body).astype(np.uint8) * 255
    cool_mask = cv2.morphologyEx(cool_mask, cv2.MORPH_OPEN, open_kernel)
    cool_near_warm = cv2.bitwise_and(
        cool_mask,
        cv2.dilate(warm_mask, np.ones((5, 5), np.uint8), iterations=1),
    )
    cool_islands = _drop_background_components(cool_mask, bgr.shape, drop_edge_touching=True)
    mask = cv2.bitwise_or(warm_mask, cv2.bitwise_or(cool_near_warm, cool_islands))
    if int(np.count_nonzero(mask)) < 10:
        mask = cv2.bitwise_or(warm_mask, cool_mask)

    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(gray, 40, 120)
    near_foreground = cv2.dilate(mask, np.ones((3, 3), np.uint8), iterations=1)
    outline = ((edges > 0) & (near_foreground > 0)).astype(np.uint8) * 255
    mask = cv2.bitwise_or(mask, outline)
    mask[blue_background] = 0
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((2, 2), np.uint8))
    return _drop_dull_isolated_components(mask, hsv)


def _drop_background_components(mask: np.ndarray, shape, drop_edge_touching: bool = False) -> np.ndarray:
    count, labels, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
    h, w = shape[:2]
    area_total = max(1, h * w)
    kept = np.zeros((h, w), dtype=np.uint8)

    for label in range(1, count):
        area = int(stats[label, cv2.CC_STAT_AREA])
        if area < 3:
            continue
        x = int(stats[label, cv2.CC_STAT_LEFT])
        y = int(stats[label, cv2.CC_STAT_TOP])
        bw = int(stats[label, cv2.CC_STAT_WIDTH])
        bh = int(stats[label, cv2.CC_STAT_HEIGHT])
        edge_touches = int(x <= 0) + int(y <= 0) + int(x + bw >= w) + int(y + bh >= h)
        area_ratio = float(area / area_total)
        if drop_edge_touching and edge_touches >= 1:
            continue
        if edge_touches >= 2 and area_ratio > 0.18:
            continue
        if edge_touches >= 3 and area_ratio > 0.08:
            continue
        kept[labels == label] = 255

    return kept


def _drop_dull_isolated_components(mask: np.ndarray, hsv: np.ndarray) -> np.ndarray:
    count, labels, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
    kept = np.zeros(mask.shape[:2], dtype=np.uint8)

    for label in range(1, count):
        area = int(stats[label, cv2.CC_STAT_AREA])
        if area < 3:
            continue
        component = labels == label
        values = hsv[component]
        mean_s = float(np.mean(values[:, 1]))
        mean_v = float(np.mean(values[:, 2]))
        if area >= 12 and mean_s < 90.0 and mean_v < 92.0:
            continue
        kept[component] = 255

    return kept


def pad_small_frame(frame: np.ndarray, templates) -> tuple[np.ndarray, tuple[int, int]]:
    if not templates:
        return frame, (0, 0)
    max_w = max(template.image.shape[1] for template in templates)
    max_h = max(template.image.shape[0] for template in templates)
    h, w = frame.shape[:2]
    pad_x = max(0, max_w + 16 - w)
    pad_y = max(0, max_h + 16 - h)
    if pad_x <= 0 and pad_y <= 0:
        return frame, (0, 0)
    left = pad_x // 2 + 12
    right = pad_x - pad_x // 2 + 12
    top = pad_y // 2 + 12
    bottom = pad_y - pad_y // 2 + 12
    padded = cv2.copyMakeBorder(frame, top, bottom, left, right, cv2.BORDER_CONSTANT, value=(49, 49, 53))
    return padded, (left, top)


def unpad_point(point: tuple[int, int], offset: tuple[int, int], shape) -> tuple[int, int]:
    h, w = shape[:2]
    x = max(0, min(w - 1, int(point[0]) - int(offset[0])))
    y = max(0, min(h - 1, int(point[1]) - int(offset[1])))
    return x, y


def unpad_bbox(bbox: tuple[int, int, int, int], offset: tuple[int, int], shape) -> tuple[int, int, int, int]:
    h, w = shape[:2]
    x, y, bw, bh = bbox
    left = max(0, min(w - 1, int(x) - int(offset[0])))
    top = max(0, min(h - 1, int(y) - int(offset[1])))
    right = max(left + 1, min(w, int(x + bw) - int(offset[0])))
    bottom = max(top + 1, min(h, int(y + bh) - int(offset[1])))
    return left, top, right - left, bottom - top
