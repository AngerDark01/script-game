from __future__ import annotations

import cv2
import numpy as np

from ..config import LootEventConfig
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
from .images import to_bgr
from .models import LootCandidate, LootPreparedTemplate, LootTemplate
from .roi import BBox, expand_bbox_to_size
from .scoring import accepted_candidate, clamp01, loot_color_score, strong_loot_evidence, weighted_score


def detect_seed_candidates(
    frame: np.ndarray,
    templates: list[LootPreparedTemplate],
    config: LootEventConfig,
    exclusion_templates: list[LootTemplate] | list[LootPreparedTemplate],
    seeds: list[BBox],
) -> list[LootCandidate]:
    bgr = to_bgr(frame)
    if bgr.size == 0 or not templates or not seeds:
        return []

    candidates: list[LootCandidate] = []
    for seed in seeds:
        candidate = _best_candidate_for_seed(bgr, templates, config, exclusion_templates, seed)
        if candidate is not None:
            candidates.append(candidate)

    candidates.sort(key=lambda item: item.score, reverse=True)
    return candidates


def _best_candidate_for_seed(
    frame: np.ndarray,
    templates: list[LootPreparedTemplate],
    config: LootEventConfig,
    exclusion_templates: list[LootTemplate] | list[LootPreparedTemplate],
    seed: BBox,
) -> LootCandidate | None:
    best: LootCandidate | None = None

    for template in templates:
        for top_left in _aligned_top_lefts(seed, template, frame.shape):
            patch = _patch_at(frame, top_left, template)
            if patch is None:
                continue

            template_score = max(
                float(_masked_color_score(patch, template)) * 0.94,
                float(_masked_gray_score(patch, template)),
            )
            shape_score = _edge_similarity(patch, template)
            color_score, color_pixels = loot_color_score(patch)
            score = weighted_score(template_score, shape_score, color_score, config)
            accepted = accepted_candidate(score, template_score, shape_score, color_score, config)

            top_x, top_y = top_left
            candidate = LootCandidate(
                score=float(score),
                template_score=float(template_score),
                shape_score=float(shape_score),
                color_score=float(color_score),
                scale=float(template.scale),
                top_left=(int(top_x), int(top_y)),
                size=(int(template.image.shape[1]), int(template.image.shape[0])),
                center=(int(top_x + template.image.shape[1] / 2), int(top_y + template.image.shape[0] / 2)),
                template_name=template.name,
                color_pixels=int(color_pixels),
                accepted=bool(accepted),
            )
            _apply_candidate_exclusions(frame, candidate, patch, config, exclusion_templates)
            if best is None or _candidate_rank(candidate) > _candidate_rank(best):
                best = candidate

    if best is None:
        return _color_only_seed_candidate(frame, seed, config)
    return best


def _apply_candidate_exclusions(
    frame: np.ndarray,
    candidate: LootCandidate,
    patch: np.ndarray,
    config: LootEventConfig,
    exclusion_templates: list[LootTemplate] | list[LootPreparedTemplate],
) -> None:
    if not candidate.accepted:
        return
    if _candidate_near_player_center(candidate, frame.shape, config):
        excluded, _ = is_player_marker_candidate(patch, exclusion_templates or [], config)
        if excluded:
            candidate.accepted = False
            return
    excluded, _ = is_gray_diamond_artifact_candidate(
        candidate.template_name,
        patch,
        shape_score=candidate.shape_score,
        template_score=candidate.template_score,
    )
    if excluded:
        candidate.accepted = False
        return
    excluded, _ = is_gold_diamond_artifact_candidate(candidate.template_name, patch, candidate.template_score)
    if excluded:
        candidate.accepted = False
        return
    excluded, _ = is_gold_sword_artifact_candidate(candidate.template_name, patch)
    if excluded:
        candidate.accepted = False
        return
    excluded, _ = is_gold_pile_artifact_candidate(candidate.template_name, patch)
    if excluded:
        candidate.accepted = False
        return
    excluded, _ = is_gold_triangle_artifact_candidate(candidate.template_name, patch)
    if excluded:
        candidate.accepted = False
        return
    excluded, _ = is_red_star_artifact_candidate(candidate.template_name, patch)
    if excluded:
        candidate.accepted = False
        return
    if not strong_loot_evidence(candidate.template_score, candidate.shape_score, candidate.color_score):
        excluded, _ = is_blue_map_artifact_candidate(patch, candidate.shape_score)
        if excluded:
            candidate.accepted = False
            return
    excluded, _ = is_white_ring_map_artifact_candidate(patch)
    if excluded:
        candidate.accepted = False


def _candidate_near_player_center(candidate: LootCandidate, shape, config: LootEventConfig) -> bool:
    height, width = shape[:2]
    radius = max(8, int(getattr(config, "player_center_mask_radius", 28)))
    center = (int(width // 2), int(height // 2))
    distance = float(np.hypot(float(candidate.center[0] - center[0]), float(candidate.center[1] - center[1])))
    return bool(distance <= float(radius))


def _aligned_top_lefts(
    seed: BBox,
    template: LootPreparedTemplate,
    shape,
) -> list[tuple[int, int]]:
    h, w = shape[:2]
    th, tw = template.image.shape[:2]
    if th > h or tw > w:
        return []

    anchors = _seed_anchor_points(seed, (tw, th))
    max_offset = max(2, min(6, min(tw, th) // 5))
    offsets = [(0, 0), (-max_offset, 0), (max_offset, 0), (0, -max_offset), (0, max_offset)]
    result: list[tuple[int, int]] = []
    seen = set()
    for center in anchors:
        base_x = int(round(center[0] - tw / 2))
        base_y = int(round(center[1] - th / 2))
        for dx, dy in offsets:
            x = max(0, min(w - tw, base_x + dx))
            y = max(0, min(h - th, base_y + dy))
            point = (int(x), int(y))
            if point not in seen:
                result.append(point)
                seen.add(point)
    return result


def _seed_anchor_points(seed: BBox, template_size: tuple[int, int]) -> list[tuple[int, int]]:
    seed_x, seed_y, seed_w, seed_h = seed
    template_w, template_h = template_size
    x_values = [float(seed_x + seed_w / 2)]
    y_values = [float(seed_y + seed_h / 2)]

    if seed_w >= max(32, int(template_w * 1.35)):
        inset = max(4.0, min(float(template_w) * 0.45, float(seed_w) / 4.0))
        x_values.extend([float(seed_x) + inset, float(seed_x + seed_w) - inset])
    if seed_h >= max(32, int(template_h * 1.35)):
        inset = max(4.0, min(float(template_h) * 0.45, float(seed_h) / 4.0))
        y_values.extend([float(seed_y) + inset, float(seed_y + seed_h) - inset])

    result: list[tuple[int, int]] = []
    seen = set()
    for x in x_values:
        for y in y_values:
            point = (int(round(x)), int(round(y)))
            if point not in seen:
                result.append(point)
                seen.add(point)
    return result[:9]


def _patch_at(frame: np.ndarray, top_left: tuple[int, int], template: LootPreparedTemplate) -> np.ndarray | None:
    x, y = top_left
    th, tw = template.image.shape[:2]
    patch = frame[y:y + th, x:x + tw]
    if patch.shape[:2] != (th, tw):
        return None
    return patch


def _masked_gray_score(patch: np.ndarray, template: LootPreparedTemplate) -> float:
    if patch.shape[:2] != template.image.shape[:2] or int(template.mask_pixels) <= 0:
        return 0.0
    patch_gray = cv2.cvtColor(to_bgr(patch), cv2.COLOR_BGR2GRAY).astype(np.float32)
    template_gray = template.gray.astype(np.float32)
    mask = template.mask > 0
    if int(np.count_nonzero(mask)) <= 0:
        return 0.0

    patch_values = patch_gray[mask]
    template_values = template_gray[mask]
    patch_values = patch_values - float(np.mean(patch_values))
    template_values = template_values - float(np.mean(template_values))
    numerator = float(np.sum(patch_values * template_values))
    patch_norm = float(np.sqrt(np.sum(patch_values * patch_values)))
    template_norm = float(np.sqrt(np.sum(template_values * template_values)))
    return clamp01((numerator / max(1e-6, patch_norm * template_norm) + 1.0) / 2.0)


def _masked_color_score(patch: np.ndarray, template: LootPreparedTemplate) -> float:
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


def _edge_similarity(patch: np.ndarray, template: LootPreparedTemplate) -> float:
    if patch.shape[:2] != template.image.shape[:2] or int(template.edge_pixels) <= 6:
        return 0.0
    patch_gray = cv2.cvtColor(to_bgr(patch), cv2.COLOR_BGR2GRAY)
    patch_edges = cv2.Canny(patch_gray, 45, 135)
    mask = cv2.dilate(template.mask, np.ones((3, 3), np.uint8), iterations=1) > 0
    template_edges = (template.edges > 0) & mask
    patch_edge_mask = (patch_edges > 0) & mask
    if int(np.count_nonzero(template_edges)) <= 0 or int(np.count_nonzero(patch_edge_mask)) <= 0:
        return 0.0
    overlap = float(np.count_nonzero(template_edges & patch_edge_mask))
    denom = float(np.sqrt(np.count_nonzero(template_edges) * np.count_nonzero(patch_edge_mask)))
    return clamp01(overlap / max(1e-6, denom))


def _color_only_seed_candidate(frame: np.ndarray, seed: BBox, config: LootEventConfig) -> LootCandidate | None:
    bbox = expand_bbox_to_size(seed, (24, 24), (frame.shape[1], frame.shape[0]))
    x, y, width, height = bbox
    patch = frame[y:y + height, x:x + width]
    color_score, color_pixels = loot_color_score(patch)
    if color_score < max(0.55, float(config.min_color_score)):
        return None
    return LootCandidate(
        score=float(color_score) * 0.5,
        template_score=0.0,
        shape_score=0.0,
        color_score=float(color_score),
        scale=1.0,
        top_left=(int(x), int(y)),
        size=(int(width), int(height)),
        center=(int(x + width / 2), int(y + height / 2)),
        template_name="color_seed",
        color_pixels=int(color_pixels),
        accepted=False,
    )


def _candidate_rank(candidate: LootCandidate) -> tuple[int, float, float]:
    return int(candidate.accepted), float(candidate.score), float(candidate.template_score)
