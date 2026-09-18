from __future__ import annotations

import cv2
import numpy as np

from ..config import LootEventConfig
from .images import to_bgr


def loot_color_score(patch: np.ndarray) -> tuple[float, int]:
    if patch.size == 0:
        return 0.0, 0
    hsv = cv2.cvtColor(to_bgr(patch), cv2.COLOR_BGR2HSV)
    h = hsv[:, :, 0]
    s = hsv[:, :, 1]
    v = hsv[:, :, 2]
    gold = (h >= 14) & (h <= 45) & (s >= 55) & (v >= 95)
    warm = ((h <= 18) | (h >= 170)) & (s >= 35) & (v >= 70)
    saturated = gold | warm
    neutral = (s <= 55) & (v >= 135)
    bright = v >= 165
    mask = saturated | neutral | bright
    pixels = int(np.count_nonzero(mask))
    area = int(patch.shape[0] * patch.shape[1])
    ratio = float(pixels / max(1, area))
    ratio_score = min(1.0, ratio / 0.18)
    pixel_score = min(1.0, pixels / 90.0)
    score = float(ratio_score * 0.72 + pixel_score * 0.28)

    saturated_pixels = int(np.count_nonzero(saturated))
    neutral_pixels = int(np.count_nonzero(neutral))
    bright_pixels = int(np.count_nonzero(bright))
    # Pure white/gray minimap outlines are bright but not loot-colored. Keep
    # enough neutral signal for gray loot templates, but do not let neutral
    # map lines receive a perfect color score.
    if saturated_pixels < max(4, int(area * 0.015)):
        neutral_ratio = float(neutral_pixels / max(1, area))
        bright_ratio = float(bright_pixels / max(1, area))
        neutral_cap = 0.38
        if neutral_ratio >= 0.18 and bright_ratio >= 0.18:
            neutral_cap = 0.28
        score = min(score, neutral_cap)
    return float(score), pixels


def weighted_score(
    template_score: float,
    shape_score: float,
    color_score: float,
    config: LootEventConfig,
) -> float:
    total_weight = max(
        0.01,
        float(config.template_weight) + float(config.shape_weight) + float(config.color_weight),
    )
    return (
        clamp01(template_score) * float(config.template_weight)
        + clamp01(shape_score) * float(config.shape_weight)
        + clamp01(color_score) * float(config.color_weight)
    ) / total_weight


def accepted_candidate(score: float, template_score: float, shape_score: float, color_score: float, config: LootEventConfig) -> bool:
    """Return whether a weighted candidate has enough evidence to be loot.

    The global threshold stays as the conservative path. Small minimap loot can
    be partially occluded or downscaled, so two stricter evidence-specific paths
    accept strong gold icons and high-confidence gray diamond icons without
    lowering the whole detector threshold.
    """
    if (
        score >= float(config.weighted_threshold)
        and color_score >= float(config.min_color_score)
        and (template_score >= float(config.min_template_score) or shape_score >= float(config.min_shape_score))
    ):
        return True

    if strong_gold_icon_candidate(template_score, shape_score, color_score):
        return True

    if strong_neutral_icon_candidate(template_score, shape_score, color_score):
        return True

    return False


def strong_loot_evidence(template_score: float, shape_score: float, color_score: float) -> bool:
    return bool(
        strong_gold_icon_candidate(template_score, shape_score, color_score)
        or strong_neutral_icon_candidate(template_score, shape_score, color_score)
    )


def strong_gold_icon_candidate(template_score: float, shape_score: float, color_score: float) -> bool:
    return bool(
        color_score >= 0.92
        and template_score >= 0.66
        and shape_score >= 0.34
    )


def strong_neutral_icon_candidate(template_score: float, shape_score: float, color_score: float) -> bool:
    return bool(
        0.36 <= color_score <= 0.50
        and template_score >= 0.78
        and shape_score >= 0.32
    )


def clamp01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))
