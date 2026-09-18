from __future__ import annotations

import cv2
import numpy as np

from ..clustering import cluster_candidates, merge_duplicate_candidates
from ..images import to_bgr
from ..models import LootCandidate, LootCluster, LootPreparedTemplate
from ..roi import BBox, expand_bbox_to_size
from ..scoring import loot_color_score
from .descriptors import (
    chamfer_similarity,
    distance_from_edges,
    edge_overlap_score,
    hog_descriptor,
    masked_template_score,
)
from .models import FeaturePreparedTemplate, FeatureScore
from .semantics import (
    accept_feature_candidate,
    is_shape_template,
    largest_body_contour,
    semantic_shape_score,
    template_kind,
)


class FeatureLootMatcher:
    """ROI-internal multi-feature sliding matcher for shape-stable loot icons."""

    def __init__(self, templates: list[LootPreparedTemplate], config) -> None:
        self.config = config
        self.templates = prepare_feature_templates(templates)

    def detect(self, frame: np.ndarray, seed_bboxes: list[BBox]) -> list[LootCluster]:
        bgr = to_bgr(frame)
        if bgr.size == 0 or not seed_bboxes or not self.templates:
            return []

        candidates: list[LootCandidate] = []
        for seed in seed_bboxes:
            for roi in self._search_rois(seed, bgr.shape):
                candidates.extend(self._scan_roi(bgr, seed, roi))

        candidates.sort(key=lambda item: item.score, reverse=True)
        limit = max(1, int(getattr(self.config, "feature_match_max_candidates", 5)))
        accepted = [candidate for candidate in merge_duplicate_candidates(candidates, limit * 4) if candidate.accepted]
        clusters = cluster_candidates(accepted)
        return clusters[: max(1, int(getattr(self.config, "max_blobs_per_frame", 3)))]

    def _search_rois(self, seed: BBox, shape) -> list[BBox]:
        max_template_w = max(template.image.shape[1] for template in self.templates)
        max_template_h = max(template.image.shape[0] for template in self.templates)
        padding = max(4, int(getattr(self.config, "feature_match_search_padding", 48)))
        window_w = max(max_template_w + 12, min(104, max(72, padding * 2)))
        window_h = max(max_template_h + 12, min(104, max(72, padding * 2)))
        rois: list[BBox] = []
        seen = set()
        for cx, cy in seed_anchor_points(seed):
            roi = expand_bbox_to_size(
                (int(round(cx - 1)), int(round(cy - 1)), 2, 2),
                (int(window_w), int(window_h)),
                (int(shape[1]), int(shape[0])),
            )
            if roi not in seen:
                rois.append(roi)
                seen.add(roi)
        return rois

    def _scan_roi(self, frame: np.ndarray, seed: BBox, roi: BBox) -> list[LootCandidate]:
        x, y, width, height = roi
        crop = frame[y:y + height, x:x + width]
        if crop.size == 0:
            return []

        roi_gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
        roi_edges = cv2.Canny(roi_gray, 45, 135)
        candidates: list[LootCandidate] = []
        top_k = max(1, int(getattr(self.config, "feature_match_top_k_per_template", 2)))
        threshold = float(getattr(self.config, "feature_match_collect_threshold", 0.38))

        for template in self.templates:
            th, tw = template.image.shape[:2]
            if th > crop.shape[0] or tw > crop.shape[1]:
                continue
            response = self._response_map(crop, roi_gray, roi_edges, template)
            suppress = max(5, min(tw, th) // 3)
            for response_score, top_left in response_hits(response, top_k, threshold, suppress):
                px, py = top_left
                patch = crop[py:py + th, px:px + tw]
                if patch.shape[:2] != (th, tw):
                    continue
                candidates.append(self._candidate_from_patch(patch, template, response_score, seed, (x + px, y + py)))

        candidates.sort(key=lambda item: item.score, reverse=True)
        return candidates

    def _response_map(
        self,
        roi: np.ndarray,
        roi_gray: np.ndarray,
        roi_edges: np.ndarray,
        template: FeaturePreparedTemplate,
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

    def _candidate_from_patch(
        self,
        patch: np.ndarray,
        template: FeaturePreparedTemplate,
        response_score: float,
        seed: BBox,
        top_left: tuple[int, int],
    ) -> LootCandidate:
        score = score_feature_patch(patch, template, response_score, self.config)
        x, y = top_left
        tw, th = int(template.image.shape[1]), int(template.image.shape[0])
        metadata_name = f"{template.name}:{template.kind}"
        return LootCandidate(
            score=float(score.score),
            template_score=float(score.template_score),
            shape_score=float(max(score.edge_score, score.chamfer_score, score.hog_score, score.contour_score)),
            color_score=float(score.color_score),
            scale=float(template.scale),
            top_left=(int(x), int(y)),
            size=(tw, th),
            center=(int(x + tw / 2), int(y + th / 2)),
            template_name=metadata_name,
            color_pixels=int(score.metrics.get("color_pixels", 0)),
            accepted=bool(score.accepted),
        )


def prepare_feature_templates(templates: list[LootPreparedTemplate]) -> list[FeaturePreparedTemplate]:
    result: list[FeaturePreparedTemplate] = []
    for template in templates:
        kind = template_kind(template.name)
        if not is_shape_template(kind):
            continue
        edge_mask = ((template.edges > 0) & (cv2.dilate(template.mask, np.ones((3, 3), np.uint8), iterations=1) > 0)).astype(np.uint8)
        result.append(
            FeaturePreparedTemplate(
                name=template.name,
                kind=kind,
                scale=float(template.scale),
                image=template.image,
                mask=template.mask,
                gray=template.gray,
                edges=template.edges,
                edge_mask=edge_mask,
                edge_distance=distance_from_edges(edge_mask),
                hog=hog_descriptor(template.gray, template.mask),
                body_contour=largest_body_contour(template.image, kind),
            )
        )
    return result


def score_feature_patch(
    patch: np.ndarray,
    template: FeaturePreparedTemplate,
    response_score: float,
    config,
) -> FeatureScore:
    template_score = masked_template_score(patch, template.image, template.mask, template.gray)
    edge_score = edge_overlap_score(patch, template.mask, template.edge_mask)
    chamfer_score = chamfer_similarity(patch, template.mask, template.edge_mask, template.edge_distance)
    hog_score = hog_similarity(patch, template)
    contour_score, semantic_score, metrics = semantic_shape_score(patch, template.kind, template.body_contour)
    color_score, color_pixels = loot_color_score(patch)
    metrics["color_pixels"] = int(color_pixels)
    score = (
        template_score * 0.20
        + edge_score * 0.18
        + chamfer_score * 0.24
        + hog_score * 0.20
        + contour_score * 0.12
        + color_score * 0.06
    )
    accepted, reason = accept_feature_candidate(
        score=score,
        template_score=template_score,
        edge_score=edge_score,
        chamfer_score=chamfer_score,
        hog_score=hog_score,
        contour_score=contour_score,
        semantic_score=semantic_score,
        color_score=color_score,
        threshold=float(getattr(config, "feature_match_threshold", 0.64)),
        kind=template.kind,
        metrics=metrics,
    )
    return FeatureScore(
        score=float(score),
        response_score=float(response_score),
        template_score=float(template_score),
        edge_score=float(edge_score),
        chamfer_score=float(chamfer_score),
        hog_score=float(hog_score),
        contour_score=float(contour_score),
        semantic_score=float(semantic_score),
        color_score=float(color_score),
        accepted=bool(accepted),
        reject_reason=str(reason),
        metrics=metrics,
    )


def hog_similarity(patch: np.ndarray, template: FeaturePreparedTemplate) -> float:
    if patch.shape[:2] != template.image.shape[:2]:
        return 0.0
    gray = cv2.cvtColor(to_bgr(patch), cv2.COLOR_BGR2GRAY)
    from .descriptors import cosine_score

    return cosine_score(hog_descriptor(gray, template.mask), template.hog)


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
