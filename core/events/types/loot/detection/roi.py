from __future__ import annotations

import cv2
import numpy as np

from ..config import LootEventConfig
from .exclusions import player_marker_color_signature, player_marker_match_scores
from .images import to_bgr
from .models import LootPreparedTemplate, LootTemplate

BBox = tuple[int, int, int, int]


def loot_roi_bboxes(
    frame: np.ndarray,
    config: LootEventConfig,
    prepared_templates: list[LootPreparedTemplate] | None = None,
) -> list[BBox]:
    """Return small image regions likely to contain loot-colored/bright blobs."""
    bgr = to_bgr(frame)
    if bgr.size == 0:
        return []

    mask = build_loot_roi_mask(bgr)
    if int(np.count_nonzero(mask)) <= 0:
        return []

    boxes = component_bboxes(mask, config, bgr.shape)
    if not boxes:
        return []

    boxes = merge_overlapping_bboxes(boxes)
    boxes = ensure_min_template_extent(boxes, bgr.shape, prepared_templates or [])
    boxes = sorted(boxes, key=lambda bbox: bbox[2] * bbox[3], reverse=True)
    max_regions = max(4, int(getattr(config, "max_blobs_per_frame", 3)) * 6)
    return boxes[:max_regions]


def loot_seed_bboxes(
    frame: np.ndarray,
    config: LootEventConfig,
    exclusion_templates: list[LootTemplate] | list[LootPreparedTemplate] | None = None,
) -> list[BBox]:
    """Return tight foreground components used as fast loot anchors."""
    bgr = to_bgr(frame)
    if bgr.size == 0:
        return []
    bgr = erase_player_center_region(bgr, config)

    seed_masks = build_loot_seed_masks(bgr)
    seed_masks = [apply_player_center_mask(mask, bgr, config, exclusion_templates or []) for mask in seed_masks]
    if not any(int(np.count_nonzero(mask)) > 0 for mask in seed_masks):
        return []

    h, w = bgr.shape[:2]
    boxes: list[BBox] = []
    min_area = max(1, int(getattr(config, "roi_min_area", 12)))
    max_size = max(8, int(getattr(config, "roi_max_size", 150)))

    for seed_mask in seed_masks:
        count, labels, stats, _ = cv2.connectedComponentsWithStats(seed_mask, connectivity=8)
        del labels
        for label in range(1, count):
            x = int(stats[label, cv2.CC_STAT_LEFT])
            y = int(stats[label, cv2.CC_STAT_TOP])
            bw = int(stats[label, cv2.CC_STAT_WIDTH])
            bh = int(stats[label, cv2.CC_STAT_HEIGHT])
            area = int(stats[label, cv2.CC_STAT_AREA])
            if area < min_area:
                continue
            if bw > max_size or bh > max_size:
                continue
            x = max(0, min(w - 1, x))
            y = max(0, min(h - 1, y))
            bw = max(1, min(w - x, bw))
            bh = max(1, min(h - y, bh))
            boxes.append((int(x), int(y), int(bw), int(bh)))

    boxes = merge_overlapping_bboxes(boxes, margin=2)
    boxes = sorted(boxes, key=lambda bbox: bbox[2] * bbox[3], reverse=True)
    max_regions = max(4, int(getattr(config, "max_blobs_per_frame", 3)) * 6)
    return boxes[:max_regions]


def erase_player_center_region(frame: np.ndarray, config: LootEventConfig) -> np.ndarray:
    """Erase the fixed minimap-center player marker before loot detection."""
    bgr = to_bgr(frame)
    if bgr.size == 0 or not bool(getattr(config, "player_center_mask_enabled", True)):
        return bgr
    result = bgr.copy()
    height, width = result.shape[:2]
    radius = max(8, int(getattr(config, "player_center_mask_radius", 28)))
    if min(width, height) <= radius * 2 + 8:
        return result
    center = (int(width // 2), int(height // 2))
    cv2.circle(result, center, int(radius), (0, 0, 0), thickness=-1)
    return result


def build_loot_seed_mask(frame: np.ndarray) -> np.ndarray:
    masks = build_loot_seed_masks(frame)
    if not masks:
        return np.zeros(to_bgr(frame).shape[:2], dtype=np.uint8)
    result = np.zeros(masks[0].shape[:2], dtype=np.uint8)
    for mask in masks:
        result = cv2.bitwise_or(result, mask)
    return result


def build_loot_seed_masks(frame: np.ndarray) -> list[np.ndarray]:
    bgr = to_bgr(frame)
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
    h = hsv[:, :, 0]
    s = hsv[:, :, 1]
    v = hsv[:, :, 2]
    gold_or_warm = (
        ((h >= 12) & (h <= 50) & (s >= 60) & (v >= 90))
        | (((h <= 22) | (h >= 168)) & (s >= 55) & (v >= 90))
    ).astype(np.uint8) * 255

    neutral = (((s <= 62) & (v >= 126)) | (v >= 164)).astype(np.uint8) * 255
    neutral_compact = _compact_neutral_seed_mask(neutral)

    open_kernel = np.ones((2, 2), np.uint8)
    close_kernel = np.ones((3, 3), np.uint8)
    masks: list[np.ndarray] = []
    for mask in (gold_or_warm, neutral_compact):
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, open_kernel)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, close_kernel)
        masks.append(mask)
    return masks


def _compact_neutral_seed_mask(neutral_mask: np.ndarray) -> np.ndarray:
    count, labels, stats, _ = cv2.connectedComponentsWithStats(neutral_mask, connectivity=8)
    result = np.zeros(neutral_mask.shape[:2], dtype=np.uint8)
    for label in range(1, count):
        x = int(stats[label, cv2.CC_STAT_LEFT])
        y = int(stats[label, cv2.CC_STAT_TOP])
        width = int(stats[label, cv2.CC_STAT_WIDTH])
        height = int(stats[label, cv2.CC_STAT_HEIGHT])
        area = int(stats[label, cv2.CC_STAT_AREA])
        bbox_area = max(1, int(width * height))
        density = float(area / bbox_area)
        aspect = float(max(width, height) / max(1, min(width, height)))
        if (
            area >= 10
            and density >= 0.32
            and aspect <= 2.4
            and width <= 42
            and height <= 42
        ):
            result[labels == label] = 255
    return result


def apply_player_center_mask(
    mask: np.ndarray,
    frame: np.ndarray,
    config: LootEventConfig,
    exclusion_templates: list[LootTemplate] | list[LootPreparedTemplate],
) -> np.ndarray:
    """Suppress the fixed center player marker before loot seed extraction."""
    if not bool(getattr(config, "player_center_mask_enabled", True)):
        return mask
    if mask.size == 0 or frame.size == 0:
        return mask

    height, width = mask.shape[:2]
    radius = max(8, int(getattr(config, "player_center_mask_radius", 28)))
    center = (int(width // 2), int(height // 2))
    patch_box = expand_bbox_to_size(
        (center[0] - radius, center[1] - radius, radius * 2, radius * 2),
        (radius * 2, radius * 2),
        (width, height),
    )
    x, y, patch_w, patch_h = patch_box
    patch = frame[y:y + patch_h, x:x + patch_w]
    if not _center_patch_looks_like_player(patch, config, exclusion_templates):
        return mask

    filtered = mask.copy()
    player_mask = _center_player_template_mask(frame, center, radius, config, exclusion_templates)
    if player_mask is not None:
        filtered[player_mask > 0] = 0
        return filtered

    cv2.circle(filtered, center, min(radius, 12), 0, thickness=-1)
    return filtered


def _center_patch_looks_like_player(
    patch: np.ndarray,
    config: LootEventConfig,
    exclusion_templates: list[LootTemplate] | list[LootPreparedTemplate],
) -> bool:
    if patch.size == 0:
        return False

    signature = player_marker_color_signature(patch)
    signature_total = (
        float(signature.get("blue_ratio", 0.0))
        + float(signature.get("gold_ratio", 0.0))
        + float(signature.get("white_ratio", 0.0))
        + float(signature.get("bright_ratio", 0.0))
    )
    if signature_total < 0.08:
        return False

    blue_ratio = float(signature.get("blue_ratio", 0.0))
    match_scores = player_marker_match_scores(patch, exclusion_templates, config.scale_values())
    template_score = float(match_scores.get("template_score", 0.0))
    structure_score = float(match_scores.get("structure_score", 0.0))

    exact_template = float(getattr(config, "player_marker_exact_template_threshold", 0.96))
    loose_template = float(getattr(config, "player_marker_template_threshold", 0.75))
    blue_threshold = float(getattr(config, "player_marker_blue_ratio_threshold", 0.30))
    return bool(
        (template_score >= exact_template and structure_score >= 0.24)
        or (blue_ratio >= blue_threshold and template_score >= loose_template and structure_score >= 0.24)
    )


def _center_player_template_mask(
    frame: np.ndarray,
    center: tuple[int, int],
    radius: int,
    config: LootEventConfig,
    exclusion_templates: list[LootTemplate] | list[LootPreparedTemplate],
) -> np.ndarray | None:
    prepared_templates = _ensure_prepared_templates(exclusion_templates, config)
    if not prepared_templates:
        return None

    bgr = to_bgr(frame)
    h, w = bgr.shape[:2]
    search_radius = max(3, min(12, int(radius) // 2))
    best_score = 0.0
    best_template = None
    best_top_left = None

    for template in prepared_templates:
        th, tw = template.image.shape[:2]
        if th > h or tw > w:
            continue
        base_x = int(round(center[0] - tw / 2))
        base_y = int(round(center[1] - th / 2))
        for dx in range(-search_radius, search_radius + 1, max(3, search_radius)):
            for dy in range(-search_radius, search_radius + 1, max(3, search_radius)):
                x = max(0, min(w - tw, base_x + dx))
                y = max(0, min(h - th, base_y + dy))
                patch = bgr[y:y + th, x:x + tw]
                if patch.shape[:2] != (th, tw):
                    continue
                score = max(_masked_color_score(patch, template), _masked_gray_score(patch, template))
                if score > best_score:
                    best_score = float(score)
                    best_template = template
                    best_top_left = (int(x), int(y))

    if best_template is None or best_top_left is None:
        return None
    if best_score < max(0.62, float(getattr(config, "player_marker_template_threshold", 0.75)) - 0.10):
        return None

    x, y = best_top_left
    th, tw = best_template.mask.shape[:2]
    full_mask = np.zeros((h, w), dtype=np.uint8)
    template_mask = cv2.dilate(best_template.mask, np.ones((3, 3), np.uint8), iterations=1)
    full_mask[y:y + th, x:x + tw] = np.maximum(full_mask[y:y + th, x:x + tw], template_mask)
    return full_mask


def _ensure_prepared_templates(
    templates: list[LootTemplate] | list[LootPreparedTemplate],
    config: LootEventConfig,
) -> list[LootPreparedTemplate]:
    if not templates:
        return []
    if all(isinstance(template, LootPreparedTemplate) for template in templates):
        return [template for template in templates if isinstance(template, LootPreparedTemplate)]
    from .templates import prepare_scaled_templates

    raw_templates = [template for template in templates if isinstance(template, LootTemplate)]
    return prepare_scaled_templates(raw_templates, config.scale_values())


def _masked_color_score(patch: np.ndarray, template: LootPreparedTemplate) -> float:
    mask = template.mask > 0
    if patch.shape[:2] != template.image.shape[:2] or int(np.count_nonzero(mask)) <= 0:
        return 0.0
    patch_values = to_bgr(patch).astype(np.float32)[mask]
    template_values = template.image.astype(np.float32)[mask]
    numerator = float(np.sum(patch_values * template_values))
    patch_norm = float(np.sqrt(np.sum(patch_values * patch_values)))
    template_norm = float(np.sqrt(np.sum(template_values * template_values)))
    return max(0.0, min(1.0, numerator / max(1e-6, patch_norm * template_norm)))


def _masked_gray_score(patch: np.ndarray, template: LootPreparedTemplate) -> float:
    mask = template.mask > 0
    if patch.shape[:2] != template.image.shape[:2] or int(np.count_nonzero(mask)) <= 0:
        return 0.0
    patch_gray = cv2.cvtColor(to_bgr(patch), cv2.COLOR_BGR2GRAY).astype(np.float32)
    template_gray = template.gray.astype(np.float32)
    patch_values = patch_gray[mask]
    template_values = template_gray[mask]
    patch_values = patch_values - float(np.mean(patch_values))
    template_values = template_values - float(np.mean(template_values))
    numerator = float(np.sum(patch_values * template_values))
    patch_norm = float(np.sqrt(np.sum(patch_values * patch_values)))
    template_norm = float(np.sqrt(np.sum(template_values * template_values)))
    return max(0.0, min(1.0, (numerator / max(1e-6, patch_norm * template_norm) + 1.0) / 2.0))


def build_loot_roi_mask(frame: np.ndarray) -> np.ndarray:
    hsv = cv2.cvtColor(to_bgr(frame), cv2.COLOR_BGR2HSV)
    h = hsv[:, :, 0]
    s = hsv[:, :, 1]
    v = hsv[:, :, 2]

    gold = (h >= 12) & (h <= 48) & (s >= 45) & (v >= 82)
    warm = ((h <= 20) | (h >= 168)) & (s >= 35) & (v >= 72)
    silver = (s <= 62) & (v >= 126)
    bright = v >= 164
    mask = (gold | warm | silver | bright).astype(np.uint8) * 255

    open_kernel = np.ones((2, 2), np.uint8)
    close_kernel = np.ones((3, 3), np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, open_kernel)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, close_kernel)
    mask = cv2.dilate(mask, close_kernel, iterations=1)
    return mask


def component_bboxes(mask: np.ndarray, config: LootEventConfig, shape) -> list[BBox]:
    count, labels, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
    del labels
    h, w = shape[:2]
    boxes: list[BBox] = []
    min_area = max(1, int(getattr(config, "roi_min_area", 12)))
    max_size = max(8, int(getattr(config, "roi_max_size", 150)))
    expand = max(0, int(getattr(config, "roi_expand", 48)))

    for label in range(1, count):
        x = int(stats[label, cv2.CC_STAT_LEFT])
        y = int(stats[label, cv2.CC_STAT_TOP])
        bw = int(stats[label, cv2.CC_STAT_WIDTH])
        bh = int(stats[label, cv2.CC_STAT_HEIGHT])
        area = int(stats[label, cv2.CC_STAT_AREA])
        if area < min_area:
            continue
        if bw > max_size or bh > max_size:
            continue
        x1 = max(0, x - expand)
        y1 = max(0, y - expand)
        x2 = min(w, x + bw + expand)
        y2 = min(h, y + bh + expand)
        if x2 <= x1 or y2 <= y1:
            continue
        boxes.append((int(x1), int(y1), int(x2 - x1), int(y2 - y1)))
    return boxes


def ensure_min_template_extent(boxes: list[BBox], shape, templates: list[LootPreparedTemplate]) -> list[BBox]:
    if not templates:
        return boxes
    min_w = min(int(template.image.shape[1]) for template in templates)
    min_h = min(int(template.image.shape[0]) for template in templates)
    h, w = shape[:2]
    result: list[BBox] = []
    for x, y, bw, bh in boxes:
        target_w = max(int(bw), int(min_w) + 4)
        target_h = max(int(bh), int(min_h) + 4)
        result.append(expand_bbox_to_size((x, y, bw, bh), (target_w, target_h), (w, h)))
    return result


def expand_bbox_to_size(bbox: BBox, size: tuple[int, int], bounds: tuple[int, int]) -> BBox:
    x, y, bw, bh = bbox
    target_w, target_h = size
    max_w, max_h = bounds
    extra_w = max(0, int(target_w) - int(bw))
    extra_h = max(0, int(target_h) - int(bh))
    x1 = max(0, int(x) - extra_w // 2)
    y1 = max(0, int(y) - extra_h // 2)
    x2 = min(max_w, x1 + max(int(bw), int(target_w)))
    y2 = min(max_h, y1 + max(int(bh), int(target_h)))
    x1 = max(0, min(x1, max_w - max(1, x2 - x1)))
    y1 = max(0, min(y1, max_h - max(1, y2 - y1)))
    return int(x1), int(y1), int(x2 - x1), int(y2 - y1)


def merge_overlapping_bboxes(boxes: list[BBox], margin: int = 8) -> list[BBox]:
    merged: list[BBox] = []
    for box in boxes:
        current = box
        changed = True
        while changed:
            changed = False
            next_merged: list[BBox] = []
            for kept in merged:
                if bboxes_touch_or_overlap(current, kept, margin=margin):
                    current = merge_two_bboxes(current, kept)
                    changed = True
                else:
                    next_merged.append(kept)
            merged = next_merged
        merged.append(current)
    return merged


def bboxes_touch_or_overlap(a: BBox, b: BBox, margin: int = 8) -> bool:
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    return bool(
        ax <= bx + bw + margin
        and ax + aw + margin >= bx
        and ay <= by + bh + margin
        and ay + ah + margin >= by
    )


def merge_two_bboxes(a: BBox, b: BBox) -> BBox:
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    x1 = min(ax, bx)
    y1 = min(ay, by)
    x2 = max(ax + aw, bx + bw)
    y2 = max(ay + ah, by + bh)
    return int(x1), int(y1), int(x2 - x1), int(y2 - y1)
