from __future__ import annotations

import cv2
import numpy as np


def filter_small_components(mask, min_area=20):
    num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(
        mask, connectivity=8
    )
    output = np.zeros_like(mask)
    for index in range(1, num_labels):
        area = stats[index, cv2.CC_STAT_AREA]
        if area >= min_area:
            output[labels == index] = 255
    return output


def extract_wall_mask(recognizer, img, is_processed=False):
    if not recognizer.enable_wall:
        return np.zeros(img.shape[:2], dtype=np.uint8)

    img_processed = img if is_processed else recognizer._preprocess_for_wall(img)

    if recognizer.transparent_mode:
        score = recognizer._compute_transparency_score(img_processed)
        _, mask = cv2.threshold(score, recognizer.trans_wall_thresh, 255, cv2.THRESH_BINARY)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, recognizer.kernel_small)
        return recognizer._filter_small_components(mask, min_area=20)

    hsv = cv2.cvtColor(img_processed, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv, recognizer.wall_hsv_min, recognizer.wall_hsv_max)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, recognizer.kernel_small)
    mask = cv2.medianBlur(mask, 3)
    mask_blur = cv2.GaussianBlur(mask, (3, 3), 0)
    _, mask = cv2.threshold(mask_blur, 127, 255, cv2.THRESH_BINARY)
    return recognizer._filter_small_components(mask, min_area=20)


def extract_fog_mask(recognizer, img, is_processed=False):
    if not recognizer.enable_fog:
        return np.zeros(img.shape[:2], dtype=np.uint8)

    img_processed = img if is_processed else recognizer._preprocess_for_fog(img)
    hsv = cv2.cvtColor(img_processed, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv, recognizer.fog_hsv_min, recognizer.fog_hsv_max)
    return cv2.morphologyEx(mask, cv2.MORPH_CLOSE, recognizer.kernel_medium)


def extract_player_mask(recognizer, img, is_processed=False):
    img_processed = img if is_processed else recognizer.preprocess_image(img)
    hsv = cv2.cvtColor(img_processed, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv, recognizer.player_hsv_min, recognizer.player_hsv_max)
    return cv2.morphologyEx(mask, cv2.MORPH_OPEN, recognizer.kernel_small)
