from __future__ import annotations

import argparse
import csv
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from time import perf_counter
from typing import Any

import cv2
import numpy as np


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.events.types.loot.assets import (  # noqa: E402
    LOOT_MINIMAP_TEMPLATES,
    LOOT_PLAYER_MARKER_EXCLUDE_TEMPLATES,
)
from core.events.types.loot.config import LootEventConfig  # noqa: E402
from core.events.types.loot.detection.images import to_bgr  # noqa: E402
from core.events.types.loot.detection.roi import BBox, expand_bbox_to_size, loot_seed_bboxes  # noqa: E402
from core.events.types.loot.detection.scoring import clamp01, loot_color_score  # noqa: E402
from core.events.types.loot.detection.templates import load_loot_templates, prepare_scaled_templates  # noqa: E402


IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".bmp", ".webp"}
SHAPE_TEMPLATE_PREFIXES = {
    "red_star": "a347e501abf4b19d45c40d8ad566d06b",
    "gold_triangle": "b1449a692babcf5adbf6ed711830b1b7",
    "gold_diamond": "b46faa109e6cd26363e9ca11ac343f90",
}


@dataclass
class ProbeTemplate:
    name: str
    kind: str
    scale: float
    image: np.ndarray
    mask: np.ndarray
    gray: np.ndarray
    edges: np.ndarray
    edge_mask: np.ndarray
    edge_distance: np.ndarray
    hog: np.ndarray
    body_contour: np.ndarray | None


@dataclass
class ProbeCandidate:
    score: float
    response_score: float
    template_score: float
    edge_score: float
    chamfer_score: float
    hog_score: float
    contour_score: float
    color_score: float
    semantic_score: float
    accepted: bool
    reject_reason: str
    template_name: str
    kind: str
    scale: float
    bbox: tuple[int, int, int, int]
    center: tuple[int, int]
    seed_bbox: tuple[int, int, int, int]
    roi_bbox: tuple[int, int, int, int]
    metrics: dict[str, Any]


def main() -> None:
    args = parse_args()
    dataset_root = resolve_path(args.dataset_root, PROJECT_ROOT)
    out_root = resolve_path(args.out_dir, PROJECT_ROOT)
    map_config_path = resolve_path(args.map_config, PROJECT_ROOT) if args.map_config else None
    config = load_config(map_config_path)
    apply_overrides(config, args)

    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = out_root / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    matcher = FeatureMatcher(
        config=config,
        threshold=float(args.threshold),
        collect_threshold=float(args.collect_threshold),
        top_k_per_template=int(args.top_k_per_template),
        max_candidates=int(args.max_candidates),
        search_padding=int(args.search_padding),
        template_mode=str(args.templates),
        scales=parse_scales(args.scales),
    )
    cases = dataset_cases(dataset_root, args.positive_dir, args.negative_dir, int(args.limit or 0))

    if int(args.workers) > 1:
        with ThreadPoolExecutor(max_workers=int(args.workers)) as executor:
            results = list(
                executor.map(
                    lambda case: evaluate_case(case, matcher, run_dir, dump_all=bool(args.dump_all)),
                    cases,
                )
            )
    else:
        results = [evaluate_case(case, matcher, run_dir, dump_all=bool(args.dump_all)) for case in cases]

    summary = build_summary(
        run_id=run_id,
        dataset_root=dataset_root,
        map_config_path=map_config_path,
        config=config,
        matcher=matcher,
        results=results,
        run_dir=run_dir,
        args=args,
    )
    write_cases_csv(run_dir / "cases.csv", results)
    write_json(run_dir / "summary.json", summary)
    write_contact_sheet(run_dir / "detections_contact_sheet.png", results)
    print_summary(summary)

    if args.strict and (summary["counts"]["fp"] or summary["counts"]["fn"]):
        raise SystemExit(1)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Probe CNN-like ROI feature matching for minimap loot icons.")
    parser.add_argument("--dataset-root", default="D:/ACloud/image/sample")
    parser.add_argument("--positive-dir", default="02_has_loot")
    parser.add_argument("--negative-dir", default="03_no_loot")
    parser.add_argument("--map-config", default="map_data/A/event_config.json")
    parser.add_argument("--out-dir", default="debug/loot_feature_match_probe")
    parser.add_argument("--templates", choices=("shape", "all"), default="shape")
    parser.add_argument("--scales", default="0.75,0.85,1.0")
    parser.add_argument("--threshold", type=float, default=0.64)
    parser.add_argument("--collect-threshold", type=float, default=0.38)
    parser.add_argument("--top-k-per-template", type=int, default=2)
    parser.add_argument("--max-candidates", type=int, default=5)
    parser.add_argument("--search-padding", type=int, default=48)
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--dump-all", action="store_true")
    parser.add_argument("--strict", action="store_true")
    return parser.parse_args()


def resolve_path(value: str, relative_base: Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else relative_base / path


def load_config(path: Path | None) -> LootEventConfig:
    raw_config: dict[str, Any] = {}
    if path is not None and path.is_file():
        with path.open("r", encoding="utf-8-sig") as handle:
            raw_config = dict(json.load(handle).get("events", {}).get("loot", {}))
    return LootEventConfig.from_dict(raw_config)


def apply_overrides(config: LootEventConfig, args: argparse.Namespace) -> None:
    config.weighted_threshold = float(args.threshold)
    config.collect_threshold = float(args.collect_threshold)


def parse_scales(raw: str) -> list[float]:
    values: list[float] = []
    for item in str(raw or "").split(","):
        item = item.strip()
        if not item:
            continue
        try:
            value = float(item)
        except ValueError:
            continue
        if value > 0:
            values.append(value)
    return values or [0.75, 0.85, 1.0]


def dataset_cases(root: Path, positive_dir: str, negative_dir: str, limit: int) -> list[dict[str, Any]]:
    positives = image_paths(root / positive_dir)
    negatives = image_paths(root / negative_dir)
    if limit > 0:
        positives = positives[:limit]
        negatives = negatives[:limit]
    if not positives and not negatives:
        raise FileNotFoundError(f"no image samples found under {root}")
    return (
        [{"path": path, "label": "has_loot", "expected": True} for path in positives]
        + [{"path": path, "label": "no_loot", "expected": False} for path in negatives]
    )


def image_paths(directory: Path) -> list[Path]:
    if not directory.is_dir():
        return []
    return sorted(
        [path for path in directory.iterdir() if path.is_file() and path.suffix.lower() in IMAGE_SUFFIXES],
        key=lambda item: item.name.lower(),
    )


class FeatureMatcher:
    def __init__(
        self,
        *,
        config: LootEventConfig,
        threshold: float,
        collect_threshold: float,
        top_k_per_template: int,
        max_candidates: int,
        search_padding: int,
        template_mode: str,
        scales: list[float],
    ) -> None:
        self.config = config
        self.threshold = float(threshold)
        self.collect_threshold = float(collect_threshold)
        self.top_k_per_template = max(1, int(top_k_per_template))
        self.max_candidates = max(1, int(max_candidates))
        self.search_padding = max(4, int(search_padding))
        self.scales = [float(scale) for scale in scales if float(scale) > 0]
        self.templates = build_probe_templates(template_mode, self.scales)
        self.exclusion_templates = prepare_scaled_templates(
            load_loot_templates(LOOT_PLAYER_MARKER_EXCLUDE_TEMPLATES),
            config.scale_values(),
        )

    def detect(self, frame: np.ndarray) -> tuple[list[ProbeCandidate], dict[str, float | int]]:
        start = perf_counter()
        bgr = to_bgr(frame)
        seed_start = perf_counter()
        seeds = loot_seed_bboxes(bgr, self.config, self.exclusion_templates)
        seed_ms = elapsed_ms(seed_start)
        if not seeds:
            return [], {"seed_ms": seed_ms, "match_ms": 0.0, "total_ms": elapsed_ms(start), "seed_count": 0}

        match_start = perf_counter()
        all_candidates: list[ProbeCandidate] = []
        for seed in seeds:
            for roi in self._search_rois(seed, bgr.shape):
                all_candidates.extend(self._scan_roi(bgr, seed, roi))

        all_candidates = merge_duplicate_candidates(all_candidates, self.max_candidates)
        match_ms = elapsed_ms(match_start)
        return all_candidates, {
            "seed_ms": seed_ms,
            "match_ms": match_ms,
            "total_ms": elapsed_ms(start),
            "seed_count": int(len(seeds)),
        }

    def _search_rois(self, seed: BBox, shape) -> list[BBox]:
        x, y, width, height = seed
        max_template_w = max(template.image.shape[1] for template in self.templates)
        max_template_h = max(template.image.shape[0] for template in self.templates)
        window_w = max(max_template_w + 12, min(104, max(72, self.search_padding * 2)))
        window_h = max(max_template_h + 12, min(104, max(72, self.search_padding * 2)))
        anchors = seed_anchor_points(seed)
        rois: list[BBox] = []
        seen = set()
        for cx, cy in anchors:
            roi = expand_bbox_to_size(
                (int(round(cx - 1)), int(round(cy - 1)), 2, 2),
                (int(window_w), int(window_h)),
                (int(shape[1]), int(shape[0])),
            )
            if roi not in seen:
                rois.append(roi)
                seen.add(roi)
        return rois

    def _scan_roi(self, frame: np.ndarray, seed: BBox, roi: BBox) -> list[ProbeCandidate]:
        x, y, width, height = roi
        crop = frame[y:y + height, x:x + width]
        if crop.size == 0:
            return []

        roi_gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
        roi_edges = cv2.Canny(roi_gray, 45, 135)
        candidates: list[ProbeCandidate] = []

        for template in self.templates:
            th, tw = template.image.shape[:2]
            if th > crop.shape[0] or tw > crop.shape[1]:
                continue
            response = self._response_map(crop, roi_gray, roi_edges, template)
            suppress = max(5, min(tw, th) // 3)
            for response_score, top_left in response_hits(
                response,
                self.top_k_per_template,
                self.collect_threshold,
                suppress,
            ):
                px, py = top_left
                patch = crop[py:py + th, px:px + tw]
                if patch.shape[:2] != (th, tw):
                    continue
                candidates.append(self._score_patch(patch, template, float(response_score), seed, roi, (x + px, y + py)))

        candidates.sort(key=lambda item: item.score, reverse=True)
        return candidates

    def _response_map(
        self,
        roi: np.ndarray,
        roi_gray: np.ndarray,
        roi_edges: np.ndarray,
        template: ProbeTemplate,
    ) -> np.ndarray:
        gray_response = cv2.matchTemplate(roi_gray, template.gray, cv2.TM_CCOEFF_NORMED)
        edge_response = cv2.matchTemplate(roi_edges, template.edges, cv2.TM_CCORR_NORMED)
        response = np.maximum(gray_response * 0.78, edge_response * 0.96)
        if int(np.count_nonzero(template.mask)) > 20:
            try:
                masked = cv2.matchTemplate(roi, template.image, cv2.TM_CCORR_NORMED, mask=template.mask)
                response = np.maximum(response, np.nan_to_num(masked) * 0.86)
            except cv2.error:
                pass
        return np.nan_to_num(response, nan=0.0, posinf=0.0, neginf=0.0)

    def _score_patch(
        self,
        patch: np.ndarray,
        template: ProbeTemplate,
        response_score: float,
        seed: BBox,
        roi: BBox,
        top_left: tuple[int, int],
    ) -> ProbeCandidate:
        template_score = masked_template_score(patch, template)
        edge_score = edge_overlap_score(patch, template)
        chamfer_score = chamfer_similarity(patch, template)
        hog_score = hog_similarity(patch, template)
        contour_score, semantic_score, metrics = semantic_shape_score(patch, template)
        color_score, _ = loot_color_score(patch)
        score = (
            template_score * 0.20
            + edge_score * 0.18
            + chamfer_score * 0.24
            + hog_score * 0.20
            + contour_score * 0.12
            + color_score * 0.06
        )
        accepted, reason = accept_candidate(
            score=score,
            template_score=template_score,
            edge_score=edge_score,
            chamfer_score=chamfer_score,
            hog_score=hog_score,
            contour_score=contour_score,
            semantic_score=semantic_score,
            color_score=color_score,
            threshold=self.threshold,
            kind=template.kind,
            metrics=metrics,
        )
        x, y = top_left
        tw, th = int(template.image.shape[1]), int(template.image.shape[0])
        return ProbeCandidate(
            score=float(score),
            response_score=float(response_score),
            template_score=float(template_score),
            edge_score=float(edge_score),
            chamfer_score=float(chamfer_score),
            hog_score=float(hog_score),
            contour_score=float(contour_score),
            color_score=float(color_score),
            semantic_score=float(semantic_score),
            accepted=bool(accepted),
            reject_reason=reason,
            template_name=template.name,
            kind=template.kind,
            scale=float(template.scale),
            bbox=(int(x), int(y), tw, th),
            center=(int(x + tw / 2), int(y + th / 2)),
            seed_bbox=tuple(int(value) for value in seed),
            roi_bbox=tuple(int(value) for value in roi),
            metrics=metrics,
        )


def build_probe_templates(template_mode: str, scales: list[float]) -> list[ProbeTemplate]:
    paths = list(LOOT_MINIMAP_TEMPLATES)
    if template_mode == "shape":
        allowed = set(SHAPE_TEMPLATE_PREFIXES.values())
        paths = [path for path in paths if path.stem in allowed]
    raw_templates = load_loot_templates(paths)
    prepared = prepare_scaled_templates(raw_templates, scales)
    result: list[ProbeTemplate] = []
    for template in prepared:
        kind = template_kind(template.name)
        if template_mode == "shape" and kind not in {"gold_diamond", "red_star", "gold_triangle"}:
            continue
        edge_mask = ((template.edges > 0) & (cv2.dilate(template.mask, np.ones((3, 3), np.uint8), iterations=1) > 0)).astype(np.uint8)
        edge_distance = distance_from_edges(edge_mask)
        result.append(
            ProbeTemplate(
                name=template.name,
                kind=kind,
                scale=float(template.scale),
                image=template.image,
                mask=template.mask,
                gray=template.gray,
                edges=template.edges,
                edge_mask=edge_mask,
                edge_distance=edge_distance,
                hog=hog_descriptor(template.gray, template.mask),
                body_contour=largest_body_contour(template.image, kind),
            )
        )
    return result


def template_kind(name: str) -> str:
    for kind, prefix in SHAPE_TEMPLATE_PREFIXES.items():
        if str(name).startswith(prefix):
            return kind
    if str(name).startswith("2bd11065656055f3e20f070fe83758f2"):
        return "gold_pile"
    if str(name).startswith("3d1c3d0f30f22b0cc723c822bb01adf7"):
        return "gold_sword"
    return "unknown"


def masked_template_score(patch: np.ndarray, template: ProbeTemplate) -> float:
    if patch.shape[:2] != template.image.shape[:2]:
        return 0.0
    mask = template.mask > 0
    if int(np.count_nonzero(mask)) <= 0:
        return 0.0
    patch_values = to_bgr(patch).astype(np.float32)[mask]
    template_values = template.image.astype(np.float32)[mask]
    color_score = cosine_score(patch_values, template_values)

    patch_gray = cv2.cvtColor(to_bgr(patch), cv2.COLOR_BGR2GRAY).astype(np.float32)
    patch_gray_values = patch_gray[mask]
    template_gray_values = template.gray.astype(np.float32)[mask]
    patch_gray_values = patch_gray_values - float(np.mean(patch_gray_values))
    template_gray_values = template_gray_values - float(np.mean(template_gray_values))
    gray_score = (cosine_score(patch_gray_values, template_gray_values) + 1.0) / 2.0
    return clamp01(max(float(color_score) * 0.94, float(gray_score)))


def edge_overlap_score(patch: np.ndarray, template: ProbeTemplate) -> float:
    if patch.shape[:2] != template.image.shape[:2]:
        return 0.0
    gray = cv2.cvtColor(to_bgr(patch), cv2.COLOR_BGR2GRAY)
    patch_edges = (cv2.Canny(gray, 45, 135) > 0) & (template.mask > 0)
    template_edges = template.edge_mask > 0
    if int(np.count_nonzero(patch_edges)) <= 0 or int(np.count_nonzero(template_edges)) <= 0:
        return 0.0
    overlap = float(np.count_nonzero(patch_edges & template_edges))
    denom = float(np.sqrt(np.count_nonzero(patch_edges) * np.count_nonzero(template_edges)))
    return clamp01(overlap / max(1e-6, denom))


def chamfer_similarity(patch: np.ndarray, template: ProbeTemplate) -> float:
    if patch.shape[:2] != template.image.shape[:2] or int(np.count_nonzero(template.edge_mask)) <= 0:
        return 0.0
    gray = cv2.cvtColor(to_bgr(patch), cv2.COLOR_BGR2GRAY)
    patch_edges = ((cv2.Canny(gray, 45, 135) > 0) & (cv2.dilate(template.mask, np.ones((3, 3), np.uint8), iterations=1) > 0)).astype(np.uint8)
    if int(np.count_nonzero(patch_edges)) <= 0:
        return 0.0
    patch_distance = distance_from_edges(patch_edges)
    t2p = float(np.mean(patch_distance[template.edge_mask > 0]))
    p2t = float(np.mean(template.edge_distance[patch_edges > 0]))
    distance = t2p * 0.65 + p2t * 0.35
    return clamp01(float(np.exp(-distance / 3.2)))


def distance_from_edges(edges: np.ndarray) -> np.ndarray:
    edge_u8 = (edges > 0).astype(np.uint8) * 255
    inv = cv2.bitwise_not(edge_u8)
    return cv2.distanceTransform(inv, cv2.DIST_L2, 3).astype(np.float32)


def hog_similarity(patch: np.ndarray, template: ProbeTemplate) -> float:
    if patch.shape[:2] != template.image.shape[:2]:
        return 0.0
    gray = cv2.cvtColor(to_bgr(patch), cv2.COLOR_BGR2GRAY)
    return cosine_score(hog_descriptor(gray, template.mask), template.hog)


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


def semantic_shape_score(patch: np.ndarray, template: ProbeTemplate) -> tuple[float, float, dict[str, Any]]:
    contour = largest_body_contour(patch, template.kind)
    metrics = contour_metrics(contour, patch.shape)
    if contour is None or template.body_contour is None:
        return 0.0, 0.0, metrics

    match_distance = float(cv2.matchShapes(template.body_contour, contour, cv2.CONTOURS_MATCH_I1, 0.0))
    match_score = clamp01(float(np.exp(-match_distance * 2.4)))
    if template.kind == "gold_diamond":
        semantic = diamond_semantic_score(metrics)
    elif template.kind == "red_star":
        semantic = star_semantic_score(metrics)
    elif template.kind == "gold_triangle":
        semantic = triangle_semantic_score(metrics)
    else:
        semantic = generic_semantic_score(metrics)
    contour_score = clamp01(match_score * 0.45 + semantic * 0.55)
    metrics["match_distance"] = round(match_distance, 4)
    metrics["match_score"] = round(match_score, 4)
    return contour_score, semantic, metrics


def largest_body_contour(image: np.ndarray, kind: str) -> np.ndarray | None:
    mask = body_mask(image, kind)
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return None
    contour = max(contours, key=cv2.contourArea)
    if float(cv2.contourArea(contour)) < 8.0:
        return None
    return contour


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
    defects = convexity_defect_count(contour, min_depth=max(1.0, min(bw, bh) * 0.04))
    return {
        "area": round(area, 3),
        "area_ratio": round(float(area / area_total), 4),
        "aspect": round(float(max(bw, bh) / max(1, min(bw, bh))), 4),
        "extent": round(float(area / max(1, bw * bh)), 4),
        "solidity": round(float(area / max(1.0, hull_area)), 4),
        "circularity": round(circularity, 4),
        "vertices": int(len(approx)),
        "defects": int(defects),
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


def accept_candidate(
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


def response_hits(response: np.ndarray, limit: int, threshold: float, suppress_radius: int) -> list[tuple[float, tuple[int, int]]]:
    hits: list[tuple[float, tuple[int, int]]] = []
    work = response.copy()
    for _ in range(max(1, int(limit))):
        _, max_val, _, max_loc = cv2.minMaxLoc(work)
        if float(max_val) < float(threshold):
            break
        hits.append((float(max_val), (int(max_loc[0]), int(max_loc[1]))))
        x, y = max_loc
        x1 = max(0, int(x) - int(suppress_radius))
        y1 = max(0, int(y) - int(suppress_radius))
        x2 = min(work.shape[1], int(x) + int(suppress_radius) + 1)
        y2 = min(work.shape[0], int(y) + int(suppress_radius) + 1)
        work[y1:y2, x1:x2] = -1.0
    return hits


def seed_anchor_points(seed: BBox) -> list[tuple[float, float]]:
    x, y, width, height = seed
    xs = [float(x + width / 2)]
    ys = [float(y + height / 2)]
    if int(width) >= 54:
        inset = max(12.0, min(float(width) / 4.0, 32.0))
        xs.extend([float(x) + inset, float(x + width) - inset])
    if int(height) >= 54:
        inset = max(12.0, min(float(height) / 4.0, 32.0))
        ys.extend([float(y) + inset, float(y + height) - inset])

    result: list[tuple[float, float]] = []
    seen = set()
    for ax in xs:
        for ay in ys:
            point = (round(float(ax), 1), round(float(ay), 1))
            if point not in seen:
                result.append((float(ax), float(ay)))
                seen.add(point)
    return result[:9]


def merge_duplicate_candidates(candidates: list[ProbeCandidate], limit: int) -> list[ProbeCandidate]:
    result: list[ProbeCandidate] = []
    for candidate in sorted(candidates, key=lambda item: item.score, reverse=True):
        if any(candidate_distance(candidate, kept) <= duplicate_radius(candidate, kept) for kept in result):
            continue
        result.append(candidate)
        if len(result) >= int(limit):
            break
    return result


def candidate_distance(a: ProbeCandidate, b: ProbeCandidate) -> float:
    return float(np.hypot(float(a.center[0] - b.center[0]), float(a.center[1] - b.center[1])))


def duplicate_radius(a: ProbeCandidate, b: ProbeCandidate) -> float:
    return max(10.0, min(a.bbox[2], a.bbox[3], b.bbox[2], b.bbox[3]) * 0.58)


def evaluate_case(case: dict[str, Any], matcher: FeatureMatcher, run_dir: Path, *, dump_all: bool) -> dict[str, Any]:
    image_path = Path(case["path"])
    frame = read_image(image_path)
    candidates, timing = matcher.detect(frame)
    accepted = [candidate for candidate in candidates if candidate.accepted]
    predicted = bool(accepted)
    expected = bool(case["expected"])
    outcome = classify_outcome(expected, predicted)

    overlay_path = ""
    crop_paths: list[str] = []
    if dump_all or outcome in {"fp", "fn"} or accepted:
        overlay_path = str(run_dir / "overlays" / outcome / f"{image_path.stem}__{outcome}.png")
        write_image(Path(overlay_path), draw_overlay(frame.copy(), candidates, expected, predicted, outcome))
        crop_paths = write_candidate_crops(frame, candidates, run_dir / "crops" / outcome, image_path.stem)

    best = accepted[0] if accepted else (candidates[0] if candidates else None)
    return {
        "image": str(image_path),
        "name": image_path.name,
        "label": str(case["label"]),
        "expected": expected,
        "predicted": predicted,
        "outcome": outcome,
        "candidate_count": int(len(candidates)),
        "accepted_count": int(len(accepted)),
        "seed_count": int(timing.get("seed_count", 0)),
        "best": candidate_to_dict(best) if best else {},
        "accepted": [candidate_to_dict(candidate) for candidate in accepted],
        "top_candidates": [candidate_to_dict(candidate) for candidate in candidates[:8]],
        "timing": {key: round(float(value), 3) for key, value in timing.items()},
        "overlay": overlay_path,
        "crops": crop_paths,
    }


def classify_outcome(expected: bool, predicted: bool) -> str:
    if expected and predicted:
        return "tp"
    if expected and not predicted:
        return "fn"
    if not expected and predicted:
        return "fp"
    return "tn"


def candidate_to_dict(candidate: ProbeCandidate | None) -> dict[str, Any]:
    if candidate is None:
        return {}
    return {
        "score": round(float(candidate.score), 6),
        "response_score": round(float(candidate.response_score), 6),
        "template_score": round(float(candidate.template_score), 6),
        "edge_score": round(float(candidate.edge_score), 6),
        "chamfer_score": round(float(candidate.chamfer_score), 6),
        "hog_score": round(float(candidate.hog_score), 6),
        "contour_score": round(float(candidate.contour_score), 6),
        "semantic_score": round(float(candidate.semantic_score), 6),
        "color_score": round(float(candidate.color_score), 6),
        "accepted": bool(candidate.accepted),
        "reject_reason": candidate.reject_reason,
        "template": candidate.template_name,
        "kind": candidate.kind,
        "scale": round(float(candidate.scale), 3),
        "bbox": [int(value) for value in candidate.bbox],
        "center": [int(value) for value in candidate.center],
        "seed_bbox": [int(value) for value in candidate.seed_bbox],
        "roi_bbox": [int(value) for value in candidate.roi_bbox],
        "metrics": candidate.metrics,
    }


def build_summary(
    *,
    run_id: str,
    dataset_root: Path,
    map_config_path: Path | None,
    config: LootEventConfig,
    matcher: FeatureMatcher,
    results: list[dict[str, Any]],
    run_dir: Path,
    args: argparse.Namespace,
) -> dict[str, Any]:
    counts = {name: sum(1 for item in results if item["outcome"] == name) for name in ("tp", "fp", "fn", "tn")}
    total = len(results)
    detect_times = [float(item["timing"]["total_ms"]) for item in results]
    match_times = [float(item["timing"]["match_ms"]) for item in results]
    return {
        "run_id": run_id,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "dataset_root": str(dataset_root),
        "map_config": str(map_config_path) if map_config_path else "",
        "outputs": {
            "run_dir": str(run_dir),
            "summary_json": str(run_dir / "summary.json"),
            "cases_csv": str(run_dir / "cases.csv"),
            "contact_sheet": str(run_dir / "detections_contact_sheet.png"),
        },
        "probe": {
            "templates": str(args.templates),
            "template_count": int(len(matcher.templates)),
            "threshold": float(args.threshold),
            "collect_threshold": float(args.collect_threshold),
            "top_k_per_template": int(args.top_k_per_template),
            "max_candidates": int(args.max_candidates),
            "search_padding": int(args.search_padding),
            "workers": int(args.workers),
            "scales": matcher.scales,
        },
        "counts": counts,
        "metrics": {
            "accuracy": ratio(counts["tp"] + counts["tn"], total),
            "precision": ratio(counts["tp"], counts["tp"] + counts["fp"]),
            "recall": ratio(counts["tp"], counts["tp"] + counts["fn"]),
            "false_positive_rate": ratio(counts["fp"], counts["fp"] + counts["tn"]),
        },
        "timing": {
            "total_ms": timing_summary(detect_times),
            "match_ms": timing_summary(match_times),
        },
        "mismatches": [item for item in results if item["outcome"] in {"fp", "fn"}],
        "cases": results,
    }


def ratio(numerator: int, denominator: int) -> float | None:
    if denominator <= 0:
        return None
    return round(float(numerator) / float(denominator), 4)


def timing_summary(values: list[float]) -> dict[str, float]:
    if not values:
        return {"avg": 0.0, "p50": 0.0, "p95": 0.0, "max": 0.0}
    ordered = sorted(float(value) for value in values)
    return {
        "avg": round(float(sum(ordered) / len(ordered)), 3),
        "p50": round(percentile(ordered, 50), 3),
        "p95": round(percentile(ordered, 95), 3),
        "max": round(float(max(ordered)), 3),
    }


def percentile(ordered: list[float], value: int) -> float:
    if not ordered:
        return 0.0
    index = int(round((len(ordered) - 1) * (value / 100.0)))
    return float(ordered[max(0, min(len(ordered) - 1, index))])


def print_summary(summary: dict[str, Any]) -> None:
    counts = summary["counts"]
    metrics = summary["metrics"]
    timing = summary["timing"]["total_ms"]
    print("Loot feature match probe complete")
    print(f"run_dir: {summary['outputs']['run_dir']}")
    print(f"counts: TP={counts['tp']} FP={counts['fp']} FN={counts['fn']} TN={counts['tn']}")
    print(
        "metrics: "
        f"precision={format_metric(metrics['precision'])} "
        f"recall={format_metric(metrics['recall'])} "
        f"fpr={format_metric(metrics['false_positive_rate'])} "
        f"accuracy={format_metric(metrics['accuracy'])}"
    )
    print(f"timing: avg={timing['avg']}ms p50={timing['p50']}ms p95={timing['p95']}ms max={timing['max']}ms")
    if summary["mismatches"]:
        print(f"mismatches: {len(summary['mismatches'])}")
        for item in summary["mismatches"][:12]:
            best = item.get("best") or {}
            print(
                f"  {item['outcome'].upper()} {item['name']} "
                f"accepted={item['accepted_count']} candidates={item['candidate_count']} "
                f"best={best.get('score')} kind={best.get('kind')} reason={best.get('reject_reason')}"
            )
    print(f"summary_json: {summary['outputs']['summary_json']}")
    print(f"cases_csv: {summary['outputs']['cases_csv']}")
    print(f"contact_sheet: {summary['outputs']['contact_sheet']}")


def format_metric(value: float | None) -> str:
    return "n/a" if value is None else f"{float(value):.4f}"


def write_cases_csv(path: Path, results: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "label",
        "expected",
        "predicted",
        "outcome",
        "candidate_count",
        "accepted_count",
        "seed_count",
        "best_score",
        "best_kind",
        "best_template",
        "best_bbox",
        "best_center",
        "best_reject_reason",
        "total_ms",
        "seed_ms",
        "match_ms",
        "image",
        "overlay",
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for item in results:
            best = item.get("best") or {}
            timing = item.get("timing") or {}
            writer.writerow(
                {
                    "label": item.get("label"),
                    "expected": item.get("expected"),
                    "predicted": item.get("predicted"),
                    "outcome": item.get("outcome"),
                    "candidate_count": item.get("candidate_count"),
                    "accepted_count": item.get("accepted_count"),
                    "seed_count": item.get("seed_count"),
                    "best_score": best.get("score", ""),
                    "best_kind": best.get("kind", ""),
                    "best_template": best.get("template", ""),
                    "best_bbox": json.dumps(best.get("bbox", []), ensure_ascii=False),
                    "best_center": json.dumps(best.get("center", []), ensure_ascii=False),
                    "best_reject_reason": best.get("reject_reason", ""),
                    "total_ms": timing.get("total_ms", ""),
                    "seed_ms": timing.get("seed_ms", ""),
                    "match_ms": timing.get("match_ms", ""),
                    "image": item.get("image"),
                    "overlay": item.get("overlay"),
                }
            )


def write_contact_sheet(path: Path, results: list[dict[str, Any]]) -> None:
    rows = []
    for item in results:
        if item["accepted_count"] <= 0:
            continue
        best = item.get("accepted", [{}])[0]
        rows.append((item, best))
    if not rows:
        return
    thumb = 130
    header = 58
    gap = 8
    columns = 5
    sheet_rows = int(np.ceil(len(rows) / columns))
    sheet = np.full((sheet_rows * (thumb + header + gap) + gap, columns * (thumb + gap) + gap, 3), 28, dtype=np.uint8)
    for index, (item, best) in enumerate(rows):
        image = read_image(Path(item["image"]))
        x, y, w, h = [int(value) for value in best["bbox"]]
        crop = image[max(0, y):min(image.shape[0], y + h), max(0, x):min(image.shape[1], x + w)]
        if crop.size == 0:
            continue
        scale = min(thumb / crop.shape[1], thumb / crop.shape[0])
        resized = cv2.resize(
            crop,
            (max(1, int(round(crop.shape[1] * scale))), max(1, int(round(crop.shape[0] * scale)))),
            interpolation=cv2.INTER_NEAREST,
        )
        tile_x = gap + (index % columns) * (thumb + gap)
        tile_y = gap + (index // columns) * (thumb + header + gap)
        cv2.putText(sheet, f"{item['name'][:3]} {item['outcome']} {best['kind']}", (tile_x, tile_y + 16), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (240, 240, 240), 1, cv2.LINE_AA)
        cv2.putText(sheet, f"s={best['score']:.2f} h={best['hog_score']:.2f} c={best['chamfer_score']:.2f}", (tile_x, tile_y + 36), cv2.FONT_HERSHEY_SIMPLEX, 0.36, (220, 220, 220), 1, cv2.LINE_AA)
        image_x = tile_x + (thumb - resized.shape[1]) // 2
        image_y = tile_y + header + (thumb - resized.shape[0]) // 2
        sheet[image_y:image_y + resized.shape[0], image_x:image_x + resized.shape[1]] = resized
        cv2.rectangle(sheet, (image_x, image_y), (image_x + resized.shape[1] - 1, image_y + resized.shape[0] - 1), (60, 220, 60), 1)
    write_image(path, sheet)


def write_candidate_crops(frame: np.ndarray, candidates: list[ProbeCandidate], out_dir: Path, stem: str) -> list[str]:
    out_dir.mkdir(parents=True, exist_ok=True)
    paths: list[str] = []
    for index, candidate in enumerate(candidates[:8]):
        x, y, w, h = candidate.bbox
        crop = frame[max(0, y):min(frame.shape[0], y + h), max(0, x):min(frame.shape[1], x + w)]
        if crop.size == 0:
            continue
        path = out_dir / f"{stem}__cand{index:02d}_{candidate.kind}_{'ok' if candidate.accepted else candidate.reject_reason}.png"
        write_image(path, crop)
        paths.append(str(path))
    return paths


def draw_overlay(frame: np.ndarray, candidates: list[ProbeCandidate], expected: bool, predicted: bool, outcome: str) -> np.ndarray:
    colors = {
        True: (0, 220, 0),
        False: (0, 165, 255),
    }
    for candidate in candidates[:12]:
        x, y, w, h = candidate.bbox
        color = colors[bool(candidate.accepted)]
        cv2.rectangle(frame, (x, y), (x + w, y + h), color, 2)
        cv2.circle(frame, candidate.center, 3, color, -1)
        label = (
            f"{candidate.kind[:3]} {candidate.score:.2f} "
            f"h{candidate.hog_score:.2f} ch{candidate.chamfer_score:.2f}"
        )
        if not candidate.accepted:
            label = f"{candidate.reject_reason[:4]} {candidate.score:.2f}"
        cv2.putText(frame, label, (x, min(frame.shape[0] - 4, y + h + 13)), cv2.FONT_HERSHEY_SIMPLEX, 0.35, color, 1, cv2.LINE_AA)
    status = f"{outcome.upper()} expected={int(expected)} predicted={int(predicted)}"
    cv2.rectangle(frame, (0, 0), (min(frame.shape[1], 340), 22), (0, 0, 0), -1)
    cv2.putText(frame, status, (4, 16), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 255), 1, cv2.LINE_AA)
    return frame


def read_image(path: Path) -> np.ndarray:
    image = cv2.imdecode(np.fromfile(str(path), dtype=np.uint8), cv2.IMREAD_UNCHANGED)
    if image is None:
        raise FileNotFoundError(path)
    return to_bgr(image)


def write_image(path: Path, image: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    ok, encoded = cv2.imencode(path.suffix or ".png", image)
    if not ok:
        raise RuntimeError(f"failed to encode image: {path}")
    encoded.tofile(str(path))


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)


def elapsed_ms(start: float) -> float:
    return (perf_counter() - start) * 1000.0


def cosine_score(a: np.ndarray, b: np.ndarray) -> float:
    av = a.astype(np.float32).reshape(-1)
    bv = b.astype(np.float32).reshape(-1)
    denom = float(np.linalg.norm(av) * np.linalg.norm(bv))
    if denom <= 1e-6:
        return 0.0
    return clamp01(float(np.dot(av, bv) / denom))


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


if __name__ == "__main__":
    main()
