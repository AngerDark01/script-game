from __future__ import annotations

import numpy as np

from core.perception.preprocessing.image_ops import gaussian_blur, median_blur, to_hsv
from core.perception.preprocessing.masks import (
    binary_threshold,
    filter_small_components as _filter_small_components,
    hsv_range_mask,
    morphology,
)


def filter_small_components(mask, min_area=20):
    return _filter_small_components(mask, min_area=min_area)


def extract_wall_mask(recognizer, img, is_processed=False):
    if not recognizer.enable_wall:
        return np.zeros(img.shape[:2], dtype=np.uint8)

    img_processed = img if is_processed else recognizer._preprocess_for_wall(img)

    if recognizer.transparent_mode:
        score = recognizer._compute_transparency_score(img_processed)
        mask = binary_threshold(score, threshold=recognizer.trans_wall_thresh)
        mask = morphology(
            mask,
            operation="close",
            kernel_shape="rect",
            kernel_size=recognizer.kernel_small.shape[0],
        )
        return recognizer._filter_small_components(mask, min_area=20)

    mask = hsv_range_mask(
        to_hsv(img_processed),
        lower=tuple(int(value) for value in recognizer.wall_hsv_min),
        upper=tuple(int(value) for value in recognizer.wall_hsv_max),
    )
    mask = morphology(
        mask,
        operation="close",
        kernel_shape="rect",
        kernel_size=recognizer.kernel_small.shape[0],
    )
    mask = median_blur(mask, kernel_size=3)
    mask_blur = gaussian_blur(mask, kernel_size=3)
    mask = binary_threshold(mask_blur, threshold=127)
    return recognizer._filter_small_components(mask, min_area=20)


def extract_fog_mask(recognizer, img, is_processed=False):
    if not recognizer.enable_fog:
        return np.zeros(img.shape[:2], dtype=np.uint8)

    img_processed = img if is_processed else recognizer._preprocess_for_fog(img)
    mask = hsv_range_mask(
        to_hsv(img_processed),
        lower=tuple(int(value) for value in recognizer.fog_hsv_min),
        upper=tuple(int(value) for value in recognizer.fog_hsv_max),
    )
    return morphology(
        mask,
        operation="close",
        kernel_shape="rect",
        kernel_size=recognizer.kernel_medium.shape[0],
    )


def extract_player_mask(recognizer, img, is_processed=False):
    img_processed = img if is_processed else recognizer.preprocess_image(img)
    mask = hsv_range_mask(
        to_hsv(img_processed),
        lower=tuple(int(value) for value in recognizer.player_hsv_min),
        upper=tuple(int(value) for value in recognizer.player_hsv_max),
    )
    return morphology(
        mask,
        operation="open",
        kernel_shape="rect",
        kernel_size=recognizer.kernel_small.shape[0],
    )
