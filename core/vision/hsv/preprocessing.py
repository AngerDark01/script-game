from __future__ import annotations

import cv2
import numpy as np


def compute_transparency_score(recognizer, img):
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    _, s, v = cv2.split(hsv)

    v_int = v.astype(np.int16)
    s_int = s.astype(np.int16)
    score_color = v_int - s_int * recognizer.trans_sat_penalty
    score_color = np.clip(score_color, 0, 255).astype(np.uint8)

    if not recognizer.tophat_enabled:
        return score_color

    kernel = cv2.getStructuringElement(
        cv2.MORPH_RECT,
        (recognizer.tophat_kernel_size, recognizer.tophat_kernel_size),
    )
    tophat = cv2.morphologyEx(v, cv2.MORPH_TOPHAT, kernel)
    tophat_boosted = cv2.convertScaleAbs(tophat, alpha=recognizer.tophat_strength, beta=0)
    return cv2.min(score_color, tophat_boosted)


def preprocess_for_wall(recognizer, img):
    if recognizer.gamma_enabled:
        table = np.array([((i / 255.0) ** recognizer.gamma_value) * 255 for i in np.arange(0, 256)]).astype("uint8")
        img = cv2.LUT(img, table)

    img_blur = cv2.GaussianBlur(img, (3, 3), 0)

    if recognizer.clahe_enabled:
        lab = cv2.cvtColor(img_blur, cv2.COLOR_BGR2LAB)
        l, a, b = cv2.split(lab)
        l2 = recognizer._clahe.apply(l)
        lab = cv2.merge((l2, a, b))
        img_enhanced = cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)
    else:
        img_enhanced = img_blur

    if recognizer.tophat_enabled:
        kernel = cv2.getStructuringElement(
            cv2.MORPH_RECT,
            (recognizer.tophat_kernel_size, recognizer.tophat_kernel_size),
        )
        tophat = cv2.morphologyEx(img_enhanced, cv2.MORPH_TOPHAT, kernel)
        img_enhanced = cv2.add(img_enhanced, tophat)

    try:
        min_val = np.percentile(img_enhanced, 40)
        max_val = np.percentile(img_enhanced, 99)
        if max_val > min_val:
            img_enhanced = np.clip((img_enhanced - min_val) * 255.0 / (max_val - min_val), 0, 255).astype(np.uint8)
    except Exception:
        pass

    if recognizer.deepen_enabled:
        img_enhanced = cv2.convertScaleAbs(img_enhanced, alpha=recognizer.deepen_factor, beta=-60)
        b, g, r = cv2.split(img_enhanced)
        b = cv2.multiply(b, recognizer.blue_boost)
        b = np.clip(b, 0, 255).astype(np.uint8)
        img_enhanced = cv2.merge((b, g, r))

    return img_enhanced


def preprocess_for_fog(recognizer, img):
    img_blur = cv2.GaussianBlur(img, (3, 3), 0)

    try:
        min_val = np.percentile(img_blur, 5)
        max_val = np.percentile(img_blur, 95)
        if max_val > min_val:
            img_enhanced = np.clip((img_blur - min_val) * 255.0 / (max_val - min_val), 0, 255).astype(np.uint8)
        else:
            img_enhanced = img_blur
    except Exception:
        img_enhanced = img_blur

    return cv2.convertScaleAbs(img_enhanced, alpha=1.1, beta=10)


def raw_gray_for_matching(recognizer, img):
    img_processed = recognizer.preprocess_image(img)
    gray = cv2.cvtColor(img_processed, cv2.COLOR_BGR2GRAY)
    h, w = gray.shape
    cv2.circle(gray, (w // 2, h // 2), 30, 0, -1)
    return gray
