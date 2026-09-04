from __future__ import annotations

import cv2
import numpy as np

from core.perception.preprocessing.image_ops import (
    add_top_hat,
    gamma_correct,
    gaussian_blur,
    lab_clahe,
    percentile_normalize,
    scale_bgr_channels,
    scale_intensity,
    to_gray,
    to_hsv,
    top_hat,
)
from core.perception.preprocessing.masks import circle_mask, subtract_mask


def compute_transparency_score(recognizer, img):
    hsv = to_hsv(img)
    _, s, v = cv2.split(hsv)

    v_int = v.astype(np.int16)
    s_int = s.astype(np.int16)
    score_color = v_int - s_int * recognizer.trans_sat_penalty
    score_color = np.clip(score_color, 0, 255).astype(np.uint8)

    if not recognizer.tophat_enabled:
        return score_color

    tophat_boosted = top_hat(
        v,
        kernel_size=recognizer.tophat_kernel_size,
        strength=recognizer.tophat_strength,
    )
    return cv2.min(score_color, tophat_boosted)


def preprocess_for_wall(recognizer, img):
    if recognizer.gamma_enabled:
        img = gamma_correct(img, gamma=recognizer.gamma_value)

    img_blur = gaussian_blur(img, kernel_size=3)

    if recognizer.clahe_enabled:
        img_enhanced = lab_clahe(
            img_blur,
            clip_limit=recognizer.clahe_clip,
            tile_grid_size=(recognizer.clahe_grid, recognizer.clahe_grid),
        )
    else:
        img_enhanced = img_blur

    if recognizer.tophat_enabled:
        img_enhanced = add_top_hat(
            img_enhanced,
            kernel_size=recognizer.tophat_kernel_size,
        )

    img_enhanced = percentile_normalize(img_enhanced, low=40, high=99)

    if recognizer.deepen_enabled:
        img_enhanced = scale_intensity(
            img_enhanced,
            alpha=recognizer.deepen_factor,
            beta=-60,
        )
        img_enhanced = scale_bgr_channels(
            img_enhanced,
            blue=recognizer.blue_boost,
        )

    return img_enhanced


def preprocess_for_fog(recognizer, img):
    img_blur = gaussian_blur(img, kernel_size=3)
    img_enhanced = percentile_normalize(img_blur, low=5, high=95)

    return scale_intensity(img_enhanced, alpha=1.1, beta=10)


def raw_gray_for_matching(recognizer, img):
    img_processed = recognizer.preprocess_image(img)
    gray = to_gray(img_processed)
    h, w = gray.shape
    return subtract_mask(
        gray,
        circle_mask(gray.shape, center=(w // 2, h // 2), radius=30),
    )
