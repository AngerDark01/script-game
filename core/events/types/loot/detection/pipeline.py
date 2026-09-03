from __future__ import annotations

import cv2
import numpy as np

from ..config import LootEventConfig
from .clustering import cluster_candidates, merge_duplicate_candidates
from .exclusions import (
    is_blue_map_artifact_candidate,
    is_gold_diamond_artifact_candidate,
    is_gold_pile_artifact_candidate,
    is_gold_sword_artifact_candidate,
    is_gold_triangle_artifact_candidate,
    is_gray_diamond_artifact_candidate,
    is_player_marker_candidate,
    is_red_star_artifact_candidate,
    is_white_ring_map_artifact_candidate,
)
from .images import pad_small_frame, to_bgr, unpad_bbox, unpad_point
from .models import LootCandidate, LootCluster, LootPreparedTemplate, LootTemplate
from .roi import BBox, erase_player_center_region, loot_roi_bboxes, loot_seed_bboxes
from .scoring import accepted_candidate, clamp01, loot_color_score, strong_loot_evidence, weighted_score
from .seed_scan import detect_seed_candidates


def detect_loot_presence(
    frame: np.ndarray,
    config: LootEventConfig,
    exclusion_templates: list[LootTemplate] | list[LootPreparedTemplate] | None = None,
) -> list[BBox]:
    """Cheap first-stage check: return suspicious loot seed regions only."""
    if frame is None:
        return []
    return loot_seed_bboxes(to_bgr(frame), config, exclusion_templates or [])


def detect_loot_blobs(
    frame: np.ndarray,
    templates: list[LootTemplate] | list[LootPreparedTemplate],
    config: LootEventConfig,
    exclusion_templates: list[LootTemplate] | None = None,
    seed_bboxes: list[BBox] | None = None,
) -> list[LootCluster]:
    frame = to_bgr(frame)
    source_shape = frame.shape
    padded_frame, offset = pad_small_frame(frame, templates)
    padded_seeds = _pad_bboxes(seed_bboxes or [], offset) if seed_bboxes is not None else None
    candidates = detect_loot_candidates(padded_frame, templates, config, exclusion_templates or [], padded_seeds)
    accepted = [candidate for candidate in candidates if candidate.accepted]
    clusters = cluster_candidates(accepted)
    clusters = [_unpad_cluster(cluster, offset, source_shape) for cluster in clusters]
    return clusters[: max(1, int(config.max_blobs_per_frame))]


def detect_loot_candidates(
    frame: np.ndarray,
    templates: list[LootTemplate] | list[LootPreparedTemplate],
    config: LootEventConfig,
    exclusion_templates: list[LootTemplate] | None = None,
    seed_bboxes: list[BBox] | None = None,
) -> list[LootCandidate]:
    frame = to_bgr(frame)
    prepared_templates = [_prepared_template(template) for template in templates]
    if bool(getattr(config, "roi_prefilter_enabled", True)):
        seeds = seed_bboxes if seed_bboxes is not None else loot_seed_bboxes(frame, config, exclusion_templates or [])
        if not seeds:
            return []
        candidates = detect_seed_candidates(frame, prepared_templates, config, exclusion_templates or [], seeds)
        return merge_duplicate_candidates(candidates, max(1, int(config.max_blobs_per_frame) * 4))
    return _detect_candidates_in_region(frame, prepared_templates, config, exclusion_templates or [], (0, 0))


def _detect_candidates_in_rois(
    frame: np.ndarray,
    templates: list[LootPreparedTemplate],
    config: LootEventConfig,
    exclusion_templates: list[LootTemplate],
    rois: list[BBox],
) -> list[LootCandidate]:
    candidates: list[LootCandidate] = []
    for x, y, width, height in rois:
        crop = frame[y:y + height, x:x + width]
        if crop.size == 0:
            continue
        candidates.extend(_detect_candidates_in_region(crop, templates, config, exclusion_templates, (x, y)))
    candidates.sort(key=lambda item: item.score, reverse=True)
    limit = int(config.top_k_per_template) * max(1, len(templates))
    return merge_duplicate_candidates(candidates, limit)


def _detect_candidates_in_region(
    frame: np.ndarray,
    templates: list[LootPreparedTemplate],
    config: LootEventConfig,
    exclusion_templates: list[LootTemplate],
    offset: tuple[int, int],
) -> list[LootCandidate]:
    frame_gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    frame_edges = cv2.Canny(frame_gray, 45, 135)
    candidates: list[LootCandidate] = []

    for prepared in templates:
        th, tw = prepared.gray.shape[:2]
        if th > frame.shape[0] or tw > frame.shape[1]:
            continue

        gray_response = cv2.matchTemplate(frame_gray, prepared.gray, cv2.TM_CCOEFF_NORMED)
        masked_response = _masked_template_response(frame, prepared, config)
        edge_response = np.zeros_like(gray_response)
        if prepared.edge_pixels > 6:
            edge_response = cv2.matchTemplate(frame_edges, prepared.edges, cv2.TM_CCOEFF_NORMED)

        response = np.maximum(gray_response * 0.72, edge_response * 0.9)
        if masked_response is not None:
            response = np.maximum(response, masked_response)

        suppress = max(6, min(tw, th) // 2)
        for _, top_left in response_hits(response, int(config.top_k_per_template), float(config.collect_threshold), suppress):
            x, y = top_left
            patch = frame[y:y + th, x:x + tw]
            template_score = _template_score_for_hit(prepared, patch, response, (x, y), config)
            shape_score = clamp01(float(edge_response[y, x]))
            color_score, color_pixels = loot_color_score(patch)
            score = weighted_score(template_score, shape_score, color_score, config)
            accepted = accepted_candidate(score, template_score, shape_score, color_score, config)
            if accepted:
                excluded, _ = is_player_marker_candidate(patch, exclusion_templates or [], config)
                if excluded and _point_near_region_center((x + tw / 2, y + th / 2), frame.shape, config):
                    accepted = False
            if accepted:
                excluded, _ = is_gray_diamond_artifact_candidate(
                    prepared.name,
                    patch,
                    shape_score=shape_score,
                    template_score=template_score,
                )
                if excluded:
                    accepted = False
            if accepted:
                excluded, _ = is_gold_diamond_artifact_candidate(prepared.name, patch, template_score)
                if excluded:
                    accepted = False
            if accepted:
                excluded, _ = is_gold_sword_artifact_candidate(prepared.name, patch)
                if excluded:
                    accepted = False
            if accepted:
                excluded, _ = is_gold_pile_artifact_candidate(prepared.name, patch)
                if excluded:
                    accepted = False
            if accepted:
                excluded, _ = is_gold_triangle_artifact_candidate(prepared.name, patch)
                if excluded:
                    accepted = False
            if accepted:
                excluded, _ = is_red_star_artifact_candidate(prepared.name, patch)
                if excluded:
                    accepted = False
            if accepted:
                if not strong_loot_evidence(template_score, shape_score, color_score):
                    excluded, _ = is_blue_map_artifact_candidate(patch, shape_score)
                    if excluded:
                        accepted = False
            if accepted:
                excluded, _ = is_white_ring_map_artifact_candidate(patch)
                if excluded:
                    accepted = False
            full_x = int(x + offset[0])
            full_y = int(y + offset[1])
            candidates.append(
                LootCandidate(
                    score=float(score),
                    template_score=float(template_score),
                    shape_score=float(shape_score),
                    color_score=float(color_score),
                    scale=float(prepared.scale),
                    top_left=(full_x, full_y),
                    size=(int(tw), int(th)),
                    center=(int(full_x + tw / 2), int(full_y + th / 2)),
                    template_name=prepared.name,
                    color_pixels=int(color_pixels),
                    accepted=accepted,
                )
            )

    candidates.sort(key=lambda item: item.score, reverse=True)
    limit = int(config.top_k_per_template) * max(1, len(templates))
    return merge_duplicate_candidates(candidates, limit)


def _masked_template_response(
    frame: np.ndarray,
    template: LootPreparedTemplate,
    config: LootEventConfig,
) -> np.ndarray | None:
    if not bool(getattr(config, "masked_color_match_enabled", True)) or int(template.mask_pixels) <= 20:
        return None
    try:
        frame_gray = cv2.cvtColor(to_bgr(frame), cv2.COLOR_BGR2GRAY)
        response = cv2.matchTemplate(frame_gray, template.gray, cv2.TM_CCORR_NORMED, mask=template.mask)
    except cv2.error:
        return None
    return np.nan_to_num(response, nan=0.0, posinf=0.0, neginf=0.0)


def _template_score_for_hit(
    template: LootPreparedTemplate,
    patch: np.ndarray,
    response: np.ndarray,
    top_left: tuple[int, int],
    config: LootEventConfig,
) -> float:
    base_score = clamp01(float(response[top_left[1], top_left[0]]))
    if not bool(getattr(config, "masked_color_match_enabled", True)) or int(template.mask_pixels) <= 20:
        return base_score
    masked_score = masked_patch_score(patch, template)
    return max(base_score, float(masked_score) * 0.92)


def masked_patch_score(patch: np.ndarray, template: LootPreparedTemplate) -> float:
    if patch.shape[:2] != template.image.shape[:2]:
        return 0.0
    mask = template.mask > 0
    if int(np.count_nonzero(mask)) <= 0:
        return 0.0
    patch_values = to_bgr(patch).astype(np.float32)[mask]
    template_values = template.image.astype(np.float32)[mask]
    numerator = float(np.sum(patch_values * template_values))
    patch_norm = float(np.sqrt(np.sum(patch_values * patch_values)))
    template_norm = float(np.sqrt(np.sum(template_values * template_values)))
    return clamp01(numerator / max(1e-6, patch_norm * template_norm))


def _point_near_region_center(point: tuple[float, float], shape, config: LootEventConfig) -> bool:
    height, width = shape[:2]
    radius = max(8, int(getattr(config, "player_center_mask_radius", 28)))
    center = (float(width // 2), float(height // 2))
    distance = float(np.hypot(float(point[0]) - center[0], float(point[1]) - center[1]))
    return bool(distance <= float(radius))


def _prepared_template(template: LootTemplate | LootPreparedTemplate) -> LootPreparedTemplate:
    if isinstance(template, LootPreparedTemplate):
        return template
    gray = cv2.cvtColor(template.image, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(gray, 45, 135)
    edges = cv2.bitwise_and(edges, edges, mask=cv2.dilate(template.mask, np.ones((3, 3), np.uint8), iterations=1))
    return LootPreparedTemplate(
        name=template.name,
        scale=1.0,
        image=template.image,
        mask=template.mask,
        gray=gray,
        edges=edges,
        edge_pixels=int(np.count_nonzero(edges)),
        mask_pixels=int(np.count_nonzero(template.mask)),
    )


def _pad_bboxes(boxes: list[BBox], offset: tuple[int, int]) -> list[BBox]:
    if not boxes:
        return []
    offset_x, offset_y = offset
    return [
        (int(x + offset_x), int(y + offset_y), int(width), int(height))
        for x, y, width, height in boxes
    ]


def response_hits(response: np.ndarray, limit: int, threshold: float, suppress_radius: int):
    hits = []
    work = response.copy()
    for _ in range(max(1, int(limit))):
        _, max_val, _, max_loc = cv2.minMaxLoc(work)
        if float(max_val) < float(threshold):
            break
        hits.append((float(max_val), max_loc))
        x, y = max_loc
        x1 = max(0, x - suppress_radius)
        y1 = max(0, y - suppress_radius)
        x2 = min(work.shape[1], x + suppress_radius + 1)
        y2 = min(work.shape[0], y + suppress_radius + 1)
        work[y1:y2, x1:x2] = -1.0
    return hits


def _unpad_cluster(cluster: LootCluster, offset: tuple[int, int], shape) -> LootCluster:
    return LootCluster(
        score=cluster.score,
        template_score=cluster.template_score,
        shape_score=cluster.shape_score,
        color_score=cluster.color_score,
        center=unpad_point(cluster.center, offset, shape),
        bbox=unpad_bbox(cluster.bbox, offset, shape),
        candidates=cluster.candidates,
        templates=cluster.templates,
    )
