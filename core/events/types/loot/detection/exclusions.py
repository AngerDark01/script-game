from __future__ import annotations

import cv2
import numpy as np

from ..config import LootEventConfig
from .images import to_bgr
from .models import LootPreparedTemplate, LootTemplate
from .scoring import clamp01


def is_player_marker_candidate(
    patch: np.ndarray,
    exclusion_templates: list[LootTemplate] | list[LootPreparedTemplate],
    config: LootEventConfig,
) -> tuple[bool, dict]:
    if not bool(config.player_marker_exclusion_enabled) or patch.size == 0:
        return False, {}
    if _is_synthetic_padding_candidate(patch):
        return False, {
            "player_marker_template_score": 0.0,
            "player_marker_structure_score": 0.0,
            "player_marker_blue_ratio": 0.0,
            "player_marker_triangle_score": 0.0,
            "player_marker_padding_ratio": 1.0,
        }

    color_signature = player_marker_color_signature(patch)
    blue_ratio = float(color_signature["blue_ratio"])
    has_player_marker_blue = blue_ratio >= float(config.player_marker_blue_ratio_threshold)
    match_scores = player_marker_match_scores(patch, exclusion_templates, config.scale_values())
    template_score = float(match_scores["template_score"])
    structure_score = float(match_scores["structure_score"])
    triangle_score = player_marker_triangle_score(patch)
    near_template_threshold = max(0.0, float(config.player_marker_template_threshold) - 0.03)
    near_triangle_threshold = max(0.0, float(config.player_marker_triangle_score_threshold) - 0.04)

    rejected = bool(
        (template_score >= float(config.player_marker_exact_template_threshold) and structure_score >= 0.24)
        or (
            has_player_marker_blue
            and template_score >= float(config.player_marker_template_threshold)
            and structure_score >= 0.34
            and triangle_score >= near_triangle_threshold
        )
        or (
            has_player_marker_blue
            and template_score >= max(0.88, float(config.player_marker_template_threshold) + 0.10)
            and structure_score >= 0.48
            and triangle_score >= max(0.68, near_triangle_threshold)
        )
        or (
            not has_player_marker_blue
            and template_score >= max(0.86, float(config.player_marker_template_threshold) + 0.08)
            and structure_score >= 0.64
            and triangle_score >= near_triangle_threshold
        )
    )
    return rejected, {
        "player_marker_template_score": float(template_score),
        "player_marker_structure_score": float(structure_score),
        "player_marker_blue_ratio": blue_ratio,
        "player_marker_triangle_score": float(triangle_score),
    }


def _is_synthetic_padding_candidate(patch: np.ndarray) -> bool:
    bgr = to_bgr(patch)
    if bgr.size == 0:
        return False
    values = bgr.astype(np.int16)
    pad_bgr = np.array([49, 49, 53], dtype=np.int16)
    pad_gray = np.array([49, 49, 49], dtype=np.int16)
    diff_bgr = np.max(np.abs(values - pad_bgr), axis=2)
    diff_gray = np.max(np.abs(values - pad_gray), axis=2)
    padding_pixels = (diff_bgr <= 2) | (diff_gray <= 2)
    padding_ratio = float(np.count_nonzero(padding_pixels) / max(1, bgr.shape[0] * bgr.shape[1]))
    return bool(padding_ratio >= 0.45)


def is_blue_map_artifact_candidate(patch: np.ndarray, shape_score: float | None = None) -> tuple[bool, dict]:
    if patch.size == 0:
        return False, {}
    color_signature = player_marker_color_signature(patch)
    blue_ratio = float(color_signature["blue_ratio"])
    gold_ratio = float(color_signature["gold_ratio"])
    white_ratio = float(color_signature["white_ratio"])
    bright_ratio = float(color_signature.get("bright_ratio", 0.0))
    shape_value = None if shape_score is None else float(shape_score)
    rejected = bool(
        (
            blue_ratio >= 0.58
            and gold_ratio <= 0.025
            and white_ratio <= 0.12
            and bright_ratio <= 0.16
        )
        or (
            shape_value is not None
            and blue_ratio >= 0.45
            and gold_ratio <= 0.012
            and bright_ratio >= 0.18
            and shape_value <= 0.43
        )
        or (
            shape_value is not None
            and blue_ratio >= 0.50
            and gold_ratio <= 0.02
            and white_ratio >= 0.16
            and bright_ratio >= 0.20
            and shape_value <= 0.50
        )
    )
    return rejected, {
        "blue_artifact_blue_ratio": blue_ratio,
        "blue_artifact_gold_ratio": gold_ratio,
        "blue_artifact_white_ratio": white_ratio,
        "blue_artifact_bright_ratio": bright_ratio,
        "blue_artifact_shape_score": shape_value,
    }


def is_white_ring_map_artifact_candidate(patch: np.ndarray) -> tuple[bool, dict]:
    """Reject white minimap rings that can look like gray loot templates."""
    if patch.size == 0:
        return False, {}

    signature = player_marker_color_signature(patch)
    gold_ratio = float(signature.get("gold_ratio", 0.0))
    white_ratio = float(signature.get("white_ratio", 0.0))
    bright_ratio = float(signature.get("bright_ratio", 0.0))
    if gold_ratio >= 0.04 or white_ratio < 0.08 or bright_ratio < 0.08:
        return False, {
            "white_ring_gold_ratio": gold_ratio,
            "white_ring_white_ratio": white_ratio,
            "white_ring_bright_ratio": bright_ratio,
            "white_ring_area": 0.0,
            "white_ring_circularity": 0.0,
            "white_ring_fill": 0.0,
        }

    hsv = cv2.cvtColor(to_bgr(patch), cv2.COLOR_BGR2HSV)
    white = ((hsv[:, :, 1] <= 70) & (hsv[:, :, 2] >= 130)).astype(np.uint8) * 255
    white = cv2.morphologyEx(white, cv2.MORPH_OPEN, np.ones((2, 2), np.uint8))
    contours, _ = cv2.findContours(white, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    best_area = 0.0
    best_circularity = 0.0
    best_fill = 0.0
    for contour in contours:
        area = float(cv2.contourArea(contour))
        perimeter = float(cv2.arcLength(contour, True))
        if area <= best_area or area < 80.0 or perimeter <= 0.0:
            continue
        x, y, width, height = cv2.boundingRect(contour)
        rect_area = float(max(1, int(width * height)))
        circularity = float(4.0 * np.pi * area / max(1e-6, perimeter * perimeter))
        fill = float(area / rect_area)
        best_area = area
        best_circularity = circularity
        best_fill = fill

    rejected = bool(
        best_area >= 120.0
        and best_circularity >= 0.70
        and best_fill >= 0.55
    )
    return rejected, {
        "white_ring_gold_ratio": gold_ratio,
        "white_ring_white_ratio": white_ratio,
        "white_ring_bright_ratio": bright_ratio,
        "white_ring_area": best_area,
        "white_ring_circularity": best_circularity,
        "white_ring_fill": best_fill,
    }


def is_gray_diamond_artifact_candidate(
    template_name: str,
    patch: np.ndarray,
    shape_score: float | None = None,
    template_score: float | None = None,
) -> tuple[bool, dict]:
    """Reject gray-diamond fallback hits on map pillars, route lines, and scene edges."""
    if patch.size == 0 or not _is_gray_diamond_template(template_name):
        return False, {}

    signature = player_marker_color_signature(patch)
    gold_ratio = float(signature.get("gold_ratio", 0.0))
    white_ratio = float(signature.get("white_ratio", 0.0))
    blue_ratio = float(signature.get("blue_ratio", 0.0))
    bright_ratio = float(signature.get("bright_ratio", 0.0))
    red_ratio = _red_ratio(patch)
    template_value = 0.0 if template_score is None else float(template_score)
    shape_value = 0.0 if shape_score is None else float(shape_score)

    rejected = bool(
        (gold_ratio <= 0.20 and white_ratio <= 0.06)
        or shape_value <= 0.344
        or blue_ratio >= 0.801
        or (white_ratio <= 0.08 and bright_ratio <= 0.12)
        or (0.12 <= red_ratio <= 0.45)
        or (gold_ratio <= 0.005 and template_value <= 0.78)
        or (blue_ratio <= 0.50 and white_ratio >= 0.20)
        or (template_value <= 0.76 and shape_value <= 0.40)
        or (shape_value >= 0.37 and red_ratio <= 0.005)
        or (template_value <= 0.82 and bright_ratio <= 0.12)
        or (red_ratio <= 0.005 and white_ratio >= 0.12)
        or (blue_ratio >= 0.60 and white_ratio >= 0.12)
    )
    return rejected, {
        "gray_diamond_artifact_template": str(template_name),
        "gray_diamond_artifact_template_score": template_value,
        "gray_diamond_artifact_gold_ratio": gold_ratio,
        "gray_diamond_artifact_red_ratio": red_ratio,
        "gray_diamond_artifact_white_ratio": white_ratio,
        "gray_diamond_artifact_blue_ratio": blue_ratio,
        "gray_diamond_artifact_bright_ratio": bright_ratio,
        "gray_diamond_artifact_shape_score": shape_value,
    }


def is_gold_diamond_artifact_candidate(
    template_name: str,
    patch: np.ndarray,
    template_score: float | None = None,
) -> tuple[bool, dict]:
    """Reject yellow-diamond hits that do not contain a real compact gold diamond."""
    if patch.size == 0 or not _is_gold_diamond_template(template_name):
        return False, {}

    metrics = gold_component_metrics(patch)
    signature = player_marker_color_signature(patch)
    gold_ratio = float(signature.get("gold_ratio", 0.0))
    white_ratio = float(signature.get("white_ratio", 0.0))
    template_value = 0.0 if template_score is None else float(template_score)
    rejected = bool(
        float(metrics["area"]) < 120.0
        or template_value < 0.745
        or float(metrics["extent"]) < 0.32
        or float(metrics["aspect"]) > 1.65
        or int(metrics["vertices"]) < 4
        or (white_ratio >= 0.18 and gold_ratio <= 0.25)
    )
    return rejected, {
        "gold_diamond_artifact_template": str(template_name),
        "gold_diamond_artifact_template_score": template_value,
        "gold_diamond_artifact_gold_ratio": gold_ratio,
        "gold_diamond_artifact_white_ratio": white_ratio,
        **{f"gold_diamond_artifact_{key}": value for key, value in metrics.items()},
    }


def is_gold_sword_artifact_candidate(template_name: str, patch: np.ndarray) -> tuple[bool, dict]:
    """Reject sword-template hits without the sword's gold body."""
    if patch.size == 0 or not _is_gold_sword_template(template_name):
        return False, {}
    metrics = gold_component_metrics(patch)
    red_ratio = _red_ratio(patch)
    rejected = bool(
        float(metrics["gold_ratio"]) < 0.035
        or float(metrics["area"]) < 12.0
        or red_ratio >= 0.10
        or float(metrics["aspect"]) < 1.45
    )
    return rejected, {
        "gold_sword_artifact_template": str(template_name),
        "gold_sword_artifact_red_ratio": red_ratio,
        **{f"gold_sword_artifact_{key}": value for key, value in metrics.items()},
    }


def is_gold_pile_artifact_candidate(template_name: str, patch: np.ndarray) -> tuple[bool, dict]:
    """Reject large gold-pile template hits on fire or red scene backgrounds."""
    if patch.size == 0 or not _is_gold_pile_template(template_name):
        return False, {}
    metrics = gold_component_metrics(patch)
    red_ratio = _red_ratio(patch)
    rejected = bool(red_ratio >= 0.25 or float(metrics["gold_ratio"]) < 0.12)
    return rejected, {
        "gold_pile_artifact_template": str(template_name),
        "gold_pile_artifact_red_ratio": red_ratio,
        **{f"gold_pile_artifact_{key}": value for key, value in metrics.items()},
    }


def is_gold_triangle_artifact_candidate(template_name: str, patch: np.ndarray) -> tuple[bool, dict]:
    """Reject triangle-template hits on red scene patches or weak gold bodies."""
    if patch.size == 0 or not _is_gold_triangle_template(template_name):
        return False, {}
    metrics = gold_component_metrics(patch)
    red_ratio = _red_ratio(patch)
    rejected = bool(
        red_ratio >= 0.12
        or float(metrics["gold_ratio"]) < 0.08
        or float(metrics["area"]) < 40.0
    )
    return rejected, {
        "gold_triangle_artifact_template": str(template_name),
        "gold_triangle_artifact_red_ratio": red_ratio,
        **{f"gold_triangle_artifact_{key}": value for key, value in metrics.items()},
    }


def is_red_star_artifact_candidate(template_name: str, patch: np.ndarray) -> tuple[bool, dict]:
    """Reject red-star hits on fire/background blobs instead of compact star icons."""
    if patch.size == 0 or not _is_red_star_template(template_name):
        return False, {}
    metrics = red_component_metrics(patch)
    area = float(metrics["area"])
    rejected = bool(
        area < 80.0
        or area > 300.0
        or float(metrics["extent"]) < 0.43
        or float(metrics["aspect"]) > 1.45
        or float(metrics["circularity"]) < 0.38
    )
    return rejected, {
        "red_star_artifact_template": str(template_name),
        **{f"red_star_artifact_{key}": value for key, value in metrics.items()},
    }


def gold_component_metrics(patch: np.ndarray) -> dict:
    bgr = to_bgr(patch)
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
    h = hsv[:, :, 0]
    s = hsv[:, :, 1]
    v = hsv[:, :, 2]
    gold = ((h >= 14) & (h <= 50) & (s >= 55) & (v >= 95)).astype(np.uint8) * 255
    gold = cv2.morphologyEx(gold, cv2.MORPH_OPEN, np.ones((2, 2), np.uint8))
    area_total = max(1, int(patch.shape[0] * patch.shape[1]))
    contours, _ = cv2.findContours(gold, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    best_area = 0.0
    best_aspect = 0.0
    best_extent = 0.0
    best_vertices = 0
    for contour in contours:
        area = float(cv2.contourArea(contour))
        if area <= best_area:
            continue
        x, y, width, height = cv2.boundingRect(contour)
        rect_area = float(max(1, int(width * height)))
        perimeter = float(cv2.arcLength(contour, True))
        approx = cv2.approxPolyDP(contour, 0.10 * perimeter, True) if perimeter > 0.0 else contour
        best_area = area
        best_aspect = float(max(width, height) / max(1, min(width, height)))
        best_extent = float(area / rect_area)
        best_vertices = int(len(approx))

    return {
        "gold_ratio": float(np.count_nonzero(gold) / area_total),
        "area": float(best_area),
        "aspect": float(best_aspect),
        "extent": float(best_extent),
        "vertices": int(best_vertices),
    }


def red_component_metrics(patch: np.ndarray) -> dict:
    bgr = to_bgr(patch)
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
    h = hsv[:, :, 0]
    s = hsv[:, :, 1]
    v = hsv[:, :, 2]
    red = (((h <= 18) | (h >= 170)) & (s >= 45) & (v >= 80)).astype(np.uint8) * 255
    red = cv2.morphologyEx(red, cv2.MORPH_OPEN, np.ones((2, 2), np.uint8))
    area_total = max(1, int(patch.shape[0] * patch.shape[1]))
    contours, _ = cv2.findContours(red, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    best_area = 0.0
    best_aspect = 0.0
    best_extent = 0.0
    best_vertices = 0
    best_circularity = 0.0
    for contour in contours:
        area = float(cv2.contourArea(contour))
        if area <= best_area:
            continue
        x, y, width, height = cv2.boundingRect(contour)
        rect_area = float(max(1, int(width * height)))
        perimeter = float(cv2.arcLength(contour, True))
        approx = cv2.approxPolyDP(contour, 0.08 * perimeter, True) if perimeter > 0.0 else contour
        best_area = area
        best_aspect = float(max(width, height) / max(1, min(width, height)))
        best_extent = float(area / rect_area)
        best_vertices = int(len(approx))
        best_circularity = float(4.0 * np.pi * area / max(1e-6, perimeter * perimeter)) if perimeter > 0.0 else 0.0

    return {
        "red_ratio": float(np.count_nonzero(red) / area_total),
        "area": float(best_area),
        "aspect": float(best_aspect),
        "extent": float(best_extent),
        "vertices": int(best_vertices),
        "circularity": float(best_circularity),
    }


def _red_ratio(patch: np.ndarray) -> float:
    hsv = cv2.cvtColor(to_bgr(patch), cv2.COLOR_BGR2HSV)
    h = hsv[:, :, 0]
    s = hsv[:, :, 1]
    v = hsv[:, :, 2]
    red = ((h <= 18) | (h >= 170)) & (s >= 35) & (v >= 70)
    area = max(1, int(patch.shape[0] * patch.shape[1]))
    return float(np.count_nonzero(red) / area)


def _is_gray_diamond_template(template_name: str) -> bool:
    return str(template_name or "").startswith("fef5a19f6713c9f973263eb8fbcff1a4")


def _is_gold_diamond_template(template_name: str) -> bool:
    return str(template_name or "").startswith("b46faa109e6cd26363e9ca11ac343f90")


def _is_gold_sword_template(template_name: str) -> bool:
    return str(template_name or "").startswith("3d1c3d0f30f22b0cc723c822bb01adf7")


def _is_gold_pile_template(template_name: str) -> bool:
    return str(template_name or "").startswith("2bd11065656055f3e20f070fe83758f2")


def _is_gold_triangle_template(template_name: str) -> bool:
    return str(template_name or "").startswith("b1449a692babcf5adbf6ed711830b1b7")


def _is_red_star_template(template_name: str) -> bool:
    return str(template_name or "").startswith("a347e501abf4b19d45c40d8ad566d06b")


def player_marker_template_score(
    patch: np.ndarray,
    templates: list[LootTemplate] | list[LootPreparedTemplate],
    scales: list[float],
) -> float:
    return float(player_marker_match_scores(patch, templates, scales)["template_score"])


def player_marker_match_scores(
    patch: np.ndarray,
    templates: list[LootTemplate] | list[LootPreparedTemplate],
    scales: list[float],
) -> dict:
    if not templates or patch.size == 0:
        return {"template_score": 0.0, "structure_score": 0.0}

    bgr = to_bgr(patch)
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    edge = cv2.Canny(gray, 45, 135)
    best_template = 0.0
    best_structure = 0.0

    for template in templates:
        for prepared in _prepared_exclusion_variants(template, scales):
            th, tw = prepared.image.shape[:2]
            if th > bgr.shape[0] or tw > bgr.shape[1]:
                continue

            response = cv2.matchTemplate(gray, prepared.gray, cv2.TM_CCOEFF_NORMED)
            _, gray_best, _, _ = cv2.minMaxLoc(response)
            gray_score = clamp01(float(gray_best))
            best_template = max(best_template, gray_score)
            best_structure = max(best_structure, gray_score)

            if int(prepared.edge_pixels) > 6:
                edge_response = cv2.matchTemplate(edge, prepared.edges, cv2.TM_CCOEFF_NORMED)
                _, edge_best, _, _ = cv2.minMaxLoc(edge_response)
                edge_score = clamp01(float(edge_best) * 0.96)
                best_template = max(best_template, edge_score)
                best_structure = max(best_structure, edge_score)

            if int(prepared.mask_pixels) > 20:
                try:
                    masked_response = cv2.matchTemplate(bgr, prepared.image, cv2.TM_CCORR_NORMED, mask=prepared.mask)
                    _, masked_best, _, _ = cv2.minMaxLoc(masked_response)
                    best_template = max(best_template, clamp01(float(masked_best) * 0.98))
                except cv2.error:
                    pass

    return {
        "template_score": float(best_template),
        "structure_score": float(best_structure),
    }


def _prepared_exclusion_variants(
    template: LootTemplate | LootPreparedTemplate,
    scales: list[float],
) -> list[LootPreparedTemplate]:
    if isinstance(template, LootPreparedTemplate):
        return [template]
    from .templates import prepare_scaled_templates

    return prepare_scaled_templates([template], sorted(set([1.0] + [float(scale) for scale in scales if scale > 0])))


def player_marker_color_signature(patch: np.ndarray) -> dict:
    hsv = cv2.cvtColor(to_bgr(patch), cv2.COLOR_BGR2HSV)
    h = hsv[:, :, 0]
    s = hsv[:, :, 1]
    v = hsv[:, :, 2]
    area = max(1, int(patch.shape[0] * patch.shape[1]))
    blue = (h >= 85) & (h <= 135) & (s >= 25) & (v >= 35) & (v <= 220)
    gold = (h >= 14) & (h <= 45) & (s >= 55) & (v >= 95)
    white = (s <= 65) & (v >= 135)
    bright = v >= 165
    return {
        "blue_ratio": float(np.count_nonzero(blue) / area),
        "gold_ratio": float(np.count_nonzero(gold) / area),
        "white_ratio": float(np.count_nonzero(white) / area),
        "bright_ratio": float(np.count_nonzero(bright) / area),
    }


def player_marker_triangle_score(patch: np.ndarray) -> float:
    bgr = to_bgr(patch)
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
    h = hsv[:, :, 0]
    s = hsv[:, :, 1]
    v = hsv[:, :, 2]
    gold_or_white = (((h >= 14) & (h <= 45) & (s >= 55) & (v >= 95)) | ((s <= 75) & (v >= 130))).astype(np.uint8) * 255
    kernel = np.ones((3, 3), np.uint8)
    mask = cv2.morphologyEx(gold_or_white, cv2.MORPH_CLOSE, kernel)
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return 0.0

    contour = max(contours, key=cv2.contourArea)
    area = float(cv2.contourArea(contour))
    if area < 12.0:
        return 0.0

    x, y, w, hgt = cv2.boundingRect(contour)
    rect_area = float(max(1, w * hgt))
    hull_area = float(max(1.0, cv2.contourArea(cv2.convexHull(contour))))
    perimeter = float(cv2.arcLength(contour, True))
    approx = cv2.approxPolyDP(contour, 0.09 * perimeter, True)

    vertices_score = 1.0 if len(approx) == 3 else (0.72 if len(approx) == 4 else 0.0)
    fill_score = clamp01((area / rect_area - 0.18) / 0.50)
    convex_score = clamp01(area / hull_area)
    aspect_score = clamp01(1.0 - abs((w / max(1.0, hgt)) - 0.70) / 0.85)
    return float(vertices_score * 0.46 + fill_score * 0.22 + convex_score * 0.20 + aspect_score * 0.12)
