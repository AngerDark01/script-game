from __future__ import annotations

import cv2
import numpy as np


def extract_combined_masks(recognizer, img, player_pos=None):
    wall_mask = recognizer.extract_walls(img, is_processed=False)
    fog_mask = recognizer.extract_fog(img, is_processed=False)

    img_wall_processed = recognizer._preprocess_for_wall(img)
    gray = cv2.cvtColor(img_wall_processed, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(gray, recognizer.edge_low, recognizer.edge_high)

    if recognizer.sat_filter_enabled:
        dynamic_mask = dynamic_color_mask(recognizer, img, player_pos=player_pos)
        wall_mask[dynamic_mask] = 0
        fog_mask[dynamic_mask] = 0
        edges[dynamic_mask] = 0

    h, w = wall_mask.shape
    if player_pos:
        cx, cy = player_pos
    else:
        cx, cy = w // 2, h // 2

    radius = int(recognizer.player_clear_radius)
    if radius > 0:
        cv2.circle(wall_mask, (cx, cy), radius, 0, -1)
        cv2.circle(fog_mask, (cx, cy), radius, 0, -1)
        cv2.circle(edges, (cx, cy), radius, 0, -1)

    match_mask = weighted_match_mask(recognizer, wall_mask, edges)
    if radius > 0:
        cv2.circle(match_mask, (cx, cy), radius, 0, -1)

    return match_mask.astype(np.uint8), wall_mask, fog_mask


def dynamic_color_mask(recognizer, img, player_pos=None):
    hsv_raw = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    _, s_raw, _ = cv2.split(hsv_raw)
    color_mask = s_raw > recognizer.sat_filter_thresh

    if recognizer.sat_filter_radius > 0:
        h_img, w_img = img.shape[:2]
        mask_radius = np.zeros((h_img, w_img), dtype=np.uint8)
        if player_pos:
            cx_p, cy_p = player_pos
        else:
            cx_p, cy_p = w_img // 2, h_img // 2
        cv2.circle(mask_radius, (cx_p, cy_p), recognizer.sat_filter_radius, 255, -1)
        color_mask = color_mask & (mask_radius > 0)

    dynamic_mask = (color_mask.astype(np.uint8) * 255)
    return cv2.dilate(dynamic_mask, recognizer.kernel_small, iterations=1) > 0


def weighted_match_mask(recognizer, wall_mask, edges):
    wall_weight = max(0, recognizer.wall_weight)
    edge_weight = max(0, recognizer.edge_weight)
    total = max(1, wall_weight + edge_weight)
    return cv2.addWeighted(
        wall_mask,
        wall_weight / total,
        edges,
        edge_weight / total,
        0,
    )
