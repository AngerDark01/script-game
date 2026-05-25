from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np

from core.events.detectors.template_matcher import TemplateSpec


@dataclass
class PortalFeatureTemplate:
    name: str
    mask: np.ndarray


@dataclass
class PortalFeatureHit:
    score: float
    mask_score: float
    density_score: float
    scale: float
    top_left: tuple[int, int]
    size: tuple[int, int]
    template_name: str
    blue_pixels: int
    template_pixels: int

    @property
    def center(self) -> tuple[int, int]:
        return (
            int(self.top_left[0] + self.size[0] / 2),
            int(self.top_left[1] + self.size[1] / 2),
        )


def portal_blue_mask(
    image: np.ndarray,
    *,
    hue_min: int = 82,
    hue_max: int = 136,
    sat_min: int = 55,
    val_min: int = 95,
) -> np.ndarray:
    if image.ndim == 2:
        bgr = cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
    else:
        bgr = image[:, :, :3]
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
    if hue_min <= hue_max:
        hue_mask = (hsv[:, :, 0] >= int(hue_min)) & (hsv[:, :, 0] <= int(hue_max))
    else:
        hue_mask = (hsv[:, :, 0] >= int(hue_min)) | (hsv[:, :, 0] <= int(hue_max))
    mask = (
        hue_mask
        & (hsv[:, :, 1] >= int(sat_min))
        & (hsv[:, :, 2] >= int(val_min))
    )
    return (mask.astype(np.uint8) * 255)


def build_feature_templates(
    templates: list[TemplateSpec],
    *,
    hue_min: int = 82,
    hue_max: int = 136,
    sat_min: int = 55,
    val_min: int = 95,
    min_template_pixels: int = 8,
) -> list[PortalFeatureTemplate]:
    feature_templates: list[PortalFeatureTemplate] = []
    for template in templates:
        mask = portal_blue_mask(
            template.image,
            hue_min=hue_min,
            hue_max=hue_max,
            sat_min=sat_min,
            val_min=val_min,
        )
        if int(np.count_nonzero(mask)) < int(min_template_pixels):
            continue
        feature_templates.append(PortalFeatureTemplate(name=template.name, mask=mask))
    return feature_templates


def match_portal_features(
    frame: np.ndarray,
    templates: list[PortalFeatureTemplate],
    scales: list[float],
    *,
    top_k: int,
    threshold: float,
    hue_min: int = 82,
    hue_max: int = 136,
    sat_min: int = 55,
    val_min: int = 95,
    min_blue_pixels: int = 36,
    max_blue_pixels: int = 420,
) -> list[PortalFeatureHit]:
    if frame is None or not templates:
        return []

    frame_mask = portal_blue_mask(
        frame,
        hue_min=hue_min,
        hue_max=hue_max,
        sat_min=sat_min,
        val_min=val_min,
    )
    frame_norm = frame_mask.astype(np.float32) / 255.0
    hits: list[PortalFeatureHit] = []
    collect_threshold = max(0.10, float(threshold) - 0.18)

    for template in templates:
        for scale in scales:
            scaled = _resize_mask(template.mask, float(scale))
            th, tw = scaled.shape[:2]
            if th >= frame_mask.shape[0] or tw >= frame_mask.shape[1]:
                continue
            template_pixels = int(np.count_nonzero(scaled))
            if template_pixels < 8:
                continue

            template_norm = scaled.astype(np.float32) / 255.0
            response = cv2.matchTemplate(frame_norm, template_norm, cv2.TM_CCOEFF_NORMED)
            response = np.nan_to_num(response, nan=-1.0, posinf=-1.0, neginf=-1.0)
            suppress = max(5, min(tw, th) // 2)
            for mask_score, top_left in _response_hits(response, top_k * 4, collect_threshold, suppress):
                x, y = top_left
                patch = frame_mask[y:y + th, x:x + tw]
                blue_pixels = int(np.count_nonzero(patch))
                if blue_pixels < int(min_blue_pixels):
                    continue
                if int(max_blue_pixels) > 0 and blue_pixels > int(max_blue_pixels):
                    continue

                density_score = min(
                    float(blue_pixels) / float(template_pixels),
                    float(template_pixels) / float(max(1, blue_pixels)),
                )
                score = float(mask_score) * 0.86 + float(density_score) * 0.14
                if score < float(threshold):
                    continue
                hits.append(
                    PortalFeatureHit(
                        score=float(score),
                        mask_score=float(mask_score),
                        density_score=float(density_score),
                        scale=float(scale),
                        top_left=(int(x), int(y)),
                        size=(int(tw), int(th)),
                        template_name=template.name,
                        blue_pixels=blue_pixels,
                        template_pixels=template_pixels,
                    )
                )

    return merge_feature_hits(hits, top_k)


def merge_feature_hits(
    hits: list[PortalFeatureHit],
    top_k: int,
    center_radius: float = 12.0,
) -> list[PortalFeatureHit]:
    selected: list[PortalFeatureHit] = []
    for hit in sorted(hits, key=lambda item: item.score, reverse=True):
        cx, cy = hit.center
        duplicate = False
        for kept in selected:
            kx, ky = kept.center
            radius = max(center_radius, min(hit.size[0], hit.size[1], kept.size[0], kept.size[1]) * 0.45)
            if float(np.hypot(cx - kx, cy - ky)) <= radius:
                duplicate = True
                break
        if not duplicate:
            selected.append(hit)
        if len(selected) >= int(top_k):
            break
    return selected


def _resize_mask(mask: np.ndarray, scale: float) -> np.ndarray:
    h, w = mask.shape[:2]
    new_w = max(4, int(round(w * float(scale))))
    new_h = max(4, int(round(h * float(scale))))
    return cv2.resize(mask, (new_w, new_h), interpolation=cv2.INTER_NEAREST)


def _response_hits(response: np.ndarray, limit: int, threshold: float, suppress_radius: int):
    hits = []
    work = response.copy()
    for _ in range(max(1, int(limit))):
        _, max_val, _, max_loc = cv2.minMaxLoc(work)
        if float(max_val) < float(threshold):
            break
        hits.append((float(max_val), max_loc))
        x, y = max_loc
        x1 = max(0, x - int(suppress_radius))
        y1 = max(0, y - int(suppress_radius))
        x2 = min(work.shape[1], x + int(suppress_radius) + 1)
        y2 = min(work.shape[0], y + int(suppress_radius) + 1)
        work[y1:y2, x1:x2] = -1.0
    return hits
