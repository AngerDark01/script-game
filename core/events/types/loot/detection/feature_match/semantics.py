from __future__ import annotations

from typing import Any

import cv2
import numpy as np

from ..images import to_bgr
from ..scoring import clamp01


def template_kind(name: str) -> str:
    if str(name).startswith("b46faa109e6cd26363e9ca11ac343f90"):
        return "gold_diamond"
    if str(name).startswith("a347e501abf4b19d45c40d8ad566d06b"):
        return "red_star"
    if str(name).startswith("b1449a692babcf5adbf6ed711830b1b7"):
        return "gold_triangle"
    if str(name).startswith("2bd11065656055f3e20f070fe83758f2"):
        return "gold_pile"
    if str(name).startswith("3d1c3d0f30f22b0cc723c822bb01adf7"):
        return "gold_sword"
    return "unknown"


def is_shape_template(kind: str) -> bool:
    return kind in {"gold_diamond", "red_star", "gold_triangle"}


def body_mask(image: np.ndarray, kind: str) -> np.ndarray:
    bgr = to_bgr(image)
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
    h = hsv[:, :, 0]
    s = hsv[:, :, 1]
    v = hsv[:, :, 2]
    if kind == "red_star":
        mask = (((h <= 18) | (h >= 168)) & (s >= 45) & (v >= 80)).astype(np.uint8) * 255
    else:
        mask = ((h >= 14) & (h <= 52) & (s >= 48) & (v >= 88)).astype(np.uint8) * 255
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((2, 2), np.uint8))
    return cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((2, 2), np.uint8))


def largest_body_contour(image: np.ndarray, kind: str) -> np.ndarray | None:
    mask = body_mask(image, kind)
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return None
    contour = max(contours, key=cv2.contourArea)
    if float(cv2.contourArea(contour)) < 8.0:
        return None
    return contour


def semantic_shape_score(patch: np.ndarray, kind: str, template_contour: np.ndarray | None) -> tuple[float, float, dict[str, Any]]:
    contour = largest_body_contour(patch, kind)
    metrics = contour_metrics(contour, patch.shape)
    if contour is None or template_contour is None:
        return 0.0, 0.0, metrics

    match_distance = float(cv2.matchShapes(template_contour, contour, cv2.CONTOURS_MATCH_I1, 0.0))
    match_score = clamp01(float(np.exp(-match_distance * 2.4)))
    if kind == "gold_diamond":
        semantic = diamond_semantic_score(metrics)
    elif kind == "red_star":
        semantic = star_semantic_score(metrics)
    elif kind == "gold_triangle":
        semantic = triangle_semantic_score(metrics)
    else:
        semantic = generic_semantic_score(metrics)
    contour_score = clamp01(match_score * 0.45 + semantic * 0.55)
    metrics["match_distance"] = round(match_distance, 4)
    metrics["match_score"] = round(match_score, 4)
    return contour_score, semantic, metrics


def contour_metrics(contour: np.ndarray | None, shape) -> dict[str, Any]:
    h, w = shape[:2]
    area_total = max(1, int(h * w))
    if contour is None:
        return {
            "area": 0.0,
            "area_ratio": 0.0,
            "aspect": 0.0,
            "extent": 0.0,
            "solidity": 0.0,
            "circularity": 0.0,
            "vertices": 0,
            "defects": 0,
            "center_x": 0.0,
            "center_y": 0.0,
        }
    area = float(cv2.contourArea(contour))
    x, y, bw, bh = cv2.boundingRect(contour)
    perimeter = float(cv2.arcLength(contour, True))
    approx = cv2.approxPolyDP(contour, 0.08 * perimeter, True) if perimeter > 0.0 else contour
    hull = cv2.convexHull(contour)
    hull_area = float(cv2.contourArea(hull))
    circularity = float(4.0 * np.pi * area / max(1e-6, perimeter * perimeter)) if perimeter > 0.0 else 0.0
    return {
        "area": round(area, 3),
        "area_ratio": round(float(area / area_total), 4),
        "aspect": round(float(max(bw, bh) / max(1, min(bw, bh))), 4),
        "extent": round(float(area / max(1, bw * bh)), 4),
        "solidity": round(float(area / max(1.0, hull_area)), 4),
        "circularity": round(circularity, 4),
        "vertices": int(len(approx)),
        "defects": int(convexity_defect_count(contour, min_depth=max(1.0, min(bw, bh) * 0.04))),
        "center_x": round(float((x + bw / 2) / max(1, w)), 4),
        "center_y": round(float((y + bh / 2) / max(1, h)), 4),
    }


def convexity_defect_count(contour: np.ndarray, min_depth: float) -> int:
    if contour is None or len(contour) < 4:
        return 0
    hull = cv2.convexHull(contour, returnPoints=False)
    if hull is None or len(hull) < 4:
        return 0
    try:
        defects = cv2.convexityDefects(contour, hull)
    except cv2.error:
        return 0
    if defects is None:
        return 0
    return int(sum(1 for defect in defects[:, 0, :] if float(defect[3]) / 256.0 >= float(min_depth)))


def accept_feature_candidate(
    *,
    score: float,
    template_score: float,
    edge_score: float,
    chamfer_score: float,
    hog_score: float,
    contour_score: float,
    semantic_score: float,
    color_score: float,
    threshold: float,
    kind: str,
    metrics: dict[str, Any],
) -> tuple[bool, str]:
    if color_score < 0.20:
        return False, "color"
    if template_score < 0.52:
        return False, "template"
    if chamfer_score < 0.45:
        return False, "chamfer"
    if hog_score < 0.42:
        return False, "hog"
    if contour_score < 0.34:
        return False, "contour"
    if kind == "red_star":
        if semantic_score < 0.60:
            return False, "star_semantic"
        if float(metrics.get("area_ratio", 0.0)) > 0.45:
            return False, "star_area"
    if kind == "gold_triangle":
        if semantic_score < 0.40:
            return False, "triangle_semantic"
        if int(metrics.get("defects", 0)) > 1:
            return False, "triangle_defects"
    if kind == "gold_diamond":
        if (
            score >= max(float(threshold), 0.72)
            and template_score >= 0.82
            and hog_score >= 0.90
            and chamfer_score >= 0.78
            and contour_score >= 0.55
        ):
            return True, ""
        if semantic_score < 0.82:
            return False, "diamond_semantic"
        if float(metrics.get("match_score", 0.0)) < 0.78:
            return False, "diamond_shape"
    if edge_score < 0.16 and chamfer_score < 0.62:
        return False, "edge"
    if score < threshold:
        return False, "score"
    return True, ""


def diamond_semantic_score(metrics: dict[str, Any]) -> float:
    area = ramp(float(metrics["area"]), 50.0, 150.0)
    aspect = ramp_down(abs(float(metrics["aspect"]) - 1.18), 0.45, 0.95)
    extent = range_score(float(metrics["extent"]), 0.34, 0.66)
    solidity = ramp(float(metrics["solidity"]), 0.72, 0.94)
    vertices = vertex_score(int(metrics["vertices"]), ideal={4}, allowed={3, 5, 6})
    center = ramp_down(abs(float(metrics["center_x"]) - 0.50), 0.20, 0.42)
    return clamp01(area * 0.18 + aspect * 0.16 + extent * 0.20 + solidity * 0.14 + vertices * 0.22 + center * 0.10)


def star_semantic_score(metrics: dict[str, Any]) -> float:
    area = range_score(float(metrics["area"]), 45.0, 380.0)
    aspect = ramp_down(abs(float(metrics["aspect"]) - 1.10), 0.45, 0.95)
    extent = range_score(float(metrics["extent"]), 0.26, 0.64)
    solidity = range_score(float(metrics["solidity"]), 0.45, 0.86)
    defects = ramp(float(metrics["defects"]), 2.0, 5.0)
    circularity = range_score(float(metrics["circularity"]), 0.24, 0.72)
    return clamp01(area * 0.16 + aspect * 0.12 + extent * 0.16 + solidity * 0.18 + defects * 0.26 + circularity * 0.12)


def triangle_semantic_score(metrics: dict[str, Any]) -> float:
    area = ramp(float(metrics["area"]), 35.0, 140.0)
    aspect = ramp_down(abs(float(metrics["aspect"]) - 1.22), 0.55, 1.10)
    extent = range_score(float(metrics["extent"]), 0.36, 0.72)
    solidity = ramp(float(metrics["solidity"]), 0.78, 0.96)
    vertices = vertex_score(int(metrics["vertices"]), ideal={3}, allowed={4, 5})
    center_y = ramp(float(metrics["center_y"]), 0.45, 0.78)
    return clamp01(area * 0.18 + aspect * 0.14 + extent * 0.18 + solidity * 0.16 + vertices * 0.20 + center_y * 0.14)


def generic_semantic_score(metrics: dict[str, Any]) -> float:
    return clamp01(
        ramp(float(metrics["area"]), 20.0, 100.0) * 0.35
        + ramp(float(metrics["solidity"]), 0.45, 0.90) * 0.30
        + range_score(float(metrics["extent"]), 0.20, 0.75) * 0.35
    )


def ramp(value: float, low: float, high: float) -> float:
    if high <= low:
        return 1.0 if value >= high else 0.0
    return clamp01((float(value) - float(low)) / (float(high) - float(low)))


def ramp_down(value: float, good: float, bad: float) -> float:
    if bad <= good:
        return 1.0 if value <= good else 0.0
    return clamp01(1.0 - (float(value) - float(good)) / (float(bad) - float(good)))


def range_score(value: float, low: float, high: float) -> float:
    center = (float(low) + float(high)) / 2.0
    radius = max(1e-6, (float(high) - float(low)) / 2.0)
    return clamp01(1.0 - abs(float(value) - center) / radius)


def vertex_score(value: int, *, ideal: set[int], allowed: set[int]) -> float:
    if int(value) in ideal:
        return 1.0
    if int(value) in allowed:
        return 0.68
    if int(value) <= 0:
        return 0.0
    return 0.25
