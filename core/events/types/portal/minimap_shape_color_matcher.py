from __future__ import annotations

from dataclasses import dataclass, field

import cv2
import numpy as np

from core.events.detectors.template_matcher import TemplateSpec


@dataclass
class PortalShapeColorParams:
    threshold: float = 0.70
    hue_min: int = 82
    hue_max: int = 136
    sat_min: int = 55
    val_min: int = 95
    outer_sat_max: int = 115
    outer_val_min: int = 105
    min_blue_pixels: int = 18
    max_blue_pixels: int = 520
    min_outer_pixels: int = 14
    min_blue_score: float = 0.28
    min_outer_score: float = 0.18
    min_shape_score: float = 0.30
    signature_min_outer_score: float = 0.45
    signature_min_edge_score: float = 0.40
    signature_min_color_score: float = 0.82
    signature_score_scale: float = 1.30


@dataclass
class PortalShapeColorHit:
    score: float
    blue_score: float
    outer_score: float
    shape_score: float
    edge_score: float
    color_score: float
    signature_score: float
    response_score: float
    scale: float
    top_left: tuple[int, int]
    size: tuple[int, int]
    template_name: str
    blue_pixels: int
    outer_pixels: int
    template_blue_pixels: int
    template_outer_pixels: int
    accepted: bool
    reject_reasons: list[str] = field(default_factory=list)

    @property
    def center(self) -> tuple[int, int]:
        return (
            int(self.top_left[0] + self.size[0] / 2),
            int(self.top_left[1] + self.size[1] / 2),
        )


@dataclass
class PortalShapeColorDebug:
    frame_blue_mask: np.ndarray
    frame_outer_mask: np.ndarray
    frame_shape_mask: np.ndarray


@dataclass
class _PreparedTemplate:
    name: str
    scale: float
    image: np.ndarray
    blue_mask: np.ndarray
    outer_mask: np.ndarray
    shape_mask: np.ndarray
    edge_mask: np.ndarray


def portal_blue_mask(
    image: np.ndarray,
    *,
    hue_min: int = 82,
    hue_max: int = 136,
    sat_min: int = 55,
    val_min: int = 95,
) -> np.ndarray:
    hsv = _to_hsv(image)
    if hue_min <= hue_max:
        hue_mask = (hsv[:, :, 0] >= int(hue_min)) & (hsv[:, :, 0] <= int(hue_max))
    else:
        hue_mask = (hsv[:, :, 0] >= int(hue_min)) | (hsv[:, :, 0] <= int(hue_max))
    mask = hue_mask & (hsv[:, :, 1] >= int(sat_min)) & (hsv[:, :, 2] >= int(val_min))
    return (mask.astype(np.uint8) * 255)


def portal_outer_mask(
    image: np.ndarray,
    *,
    sat_max: int = 115,
    val_min: int = 105,
    blue_mask: np.ndarray | None = None,
) -> np.ndarray:
    hsv = _to_hsv(image)
    mask = (hsv[:, :, 1] <= int(sat_max)) & (hsv[:, :, 2] >= int(val_min))
    if blue_mask is not None:
        mask &= blue_mask == 0
    return (mask.astype(np.uint8) * 255)


def match_portal_shape_color(
    frame: np.ndarray,
    templates: list[TemplateSpec],
    scales: list[float],
    *,
    top_k: int,
    params: PortalShapeColorParams | None = None,
    collect_threshold: float | None = None,
) -> tuple[list[PortalShapeColorHit], PortalShapeColorDebug]:
    params = params or PortalShapeColorParams()
    frame_blue = portal_blue_mask(
        frame,
        hue_min=params.hue_min,
        hue_max=params.hue_max,
        sat_min=params.sat_min,
        val_min=params.val_min,
    )
    frame_outer = portal_outer_mask(
        frame,
        sat_max=params.outer_sat_max,
        val_min=params.outer_val_min,
        blue_mask=frame_blue,
    )
    frame_shape = cv2.bitwise_or(frame_blue, frame_outer)
    frame_edges = cv2.Canny(cv2.cvtColor(_to_bgr(frame), cv2.COLOR_BGR2GRAY), 50, 150)

    hits: list[PortalShapeColorHit] = []
    threshold = float(params.threshold)
    collect = float(collect_threshold) if collect_threshold is not None else max(0.05, threshold - 0.22)

    for template in templates:
        for scale in scales:
            prepared = _prepare_template(template, float(scale), params)
            th, tw = prepared.shape_mask.shape[:2]
            if th >= frame.shape[0] or tw >= frame.shape[1]:
                continue
            if int(np.count_nonzero(prepared.blue_mask)) < 3:
                continue

            response = _combined_response(
                frame,
                frame_blue,
                frame_outer,
                frame_shape,
                frame_edges,
                prepared,
            )
            suppress = max(6, min(tw, th) // 2)
            for response_score, top_left in _response_hits(response, max(1, int(top_k)) * 5, collect, suppress):
                hit = _evaluate_candidate(
                    frame,
                    frame_blue,
                    frame_outer,
                    frame_shape,
                    frame_edges,
                    prepared,
                    top_left,
                    response_score,
                    params,
                )
                hits.append(hit)

    return merge_shape_color_hits(hits, top_k), PortalShapeColorDebug(
        frame_blue_mask=frame_blue,
        frame_outer_mask=frame_outer,
        frame_shape_mask=frame_shape,
    )


def merge_shape_color_hits(
    hits: list[PortalShapeColorHit],
    top_k: int,
    center_radius: float = 12.0,
) -> list[PortalShapeColorHit]:
    selected: list[PortalShapeColorHit] = []
    for hit in sorted(hits, key=lambda item: (item.accepted, item.score), reverse=True):
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


def _prepare_template(
    template: TemplateSpec,
    scale: float,
    params: PortalShapeColorParams,
) -> _PreparedTemplate:
    image = _resize_image(template.image, scale)
    blue = portal_blue_mask(
        image,
        hue_min=params.hue_min,
        hue_max=params.hue_max,
        sat_min=params.sat_min,
        val_min=params.val_min,
    )
    outer = portal_outer_mask(
        image,
        sat_max=params.outer_sat_max,
        val_min=params.outer_val_min,
        blue_mask=blue,
    )
    shape = cv2.bitwise_or(blue, outer)
    if template.mask is not None:
        alpha = _resize_mask(template.mask, scale)
        blue = cv2.bitwise_and(blue, alpha)
        outer = cv2.bitwise_and(outer, alpha)
        shape = cv2.bitwise_and(shape, alpha)
    edge = cv2.Canny(cv2.cvtColor(image, cv2.COLOR_BGR2GRAY), 50, 150)
    return _PreparedTemplate(
        name=template.name,
        scale=float(scale),
        image=image,
        blue_mask=blue,
        outer_mask=outer,
        shape_mask=shape,
        edge_mask=edge,
    )


def _combined_response(
    frame: np.ndarray,
    frame_blue: np.ndarray,
    frame_outer: np.ndarray,
    frame_shape: np.ndarray,
    frame_edges: np.ndarray,
    prepared: _PreparedTemplate,
) -> np.ndarray:
    blue_response = _mask_response(frame_blue, prepared.blue_mask)
    outer_response = _mask_response(frame_outer, prepared.outer_mask)
    shape_response = _mask_response(frame_shape, prepared.shape_mask)
    edge_response = _mask_response(frame_edges, prepared.edge_mask)
    color_response = _color_response(frame, prepared.image, prepared.shape_mask)
    return (
        blue_response * 0.30
        + outer_response * 0.24
        + shape_response * 0.24
        + edge_response * 0.12
        + color_response * 0.10
    )


def _evaluate_candidate(
    frame: np.ndarray,
    frame_blue: np.ndarray,
    frame_outer: np.ndarray,
    frame_shape: np.ndarray,
    frame_edges: np.ndarray,
    prepared: _PreparedTemplate,
    top_left: tuple[int, int],
    response_score: float,
    params: PortalShapeColorParams,
) -> PortalShapeColorHit:
    x, y = int(top_left[0]), int(top_left[1])
    h, w = prepared.shape_mask.shape[:2]
    blue_patch = frame_blue[y:y + h, x:x + w]
    outer_patch = frame_outer[y:y + h, x:x + w]
    shape_patch = frame_shape[y:y + h, x:x + w]
    edge_patch = frame_edges[y:y + h, x:x + w]
    frame_patch = frame[y:y + h, x:x + w]

    blue_score, blue_pixels, template_blue_pixels = _f1_score(blue_patch, prepared.blue_mask)
    outer_score, outer_pixels, template_outer_pixels = _f1_score(outer_patch, prepared.outer_mask)
    shape_score, _, _ = _f1_score(shape_patch, prepared.shape_mask)
    edge_score, _, _ = _f1_score(edge_patch, prepared.edge_mask)
    color_score = _patch_color_score(frame_patch, prepared.image, prepared.shape_mask)
    base_score = (
        blue_score * 0.31
        + outer_score * 0.25
        + shape_score * 0.25
        + edge_score * 0.11
        + color_score * 0.08
    )
    signature_ok = (
        outer_score >= float(params.signature_min_outer_score)
        and edge_score >= float(params.signature_min_edge_score)
        and color_score >= float(params.signature_min_color_score)
    )
    signature_score = 0.0
    if signature_ok:
        signature_score = min(
            1.0,
            (
                edge_score * 0.55
                + color_score * 0.30
                + outer_score * 0.15
            ) * float(params.signature_score_scale),
        )
    score = max(base_score, signature_score)

    reasons: list[str] = []
    if score < float(params.threshold):
        reasons.append("score")
    if blue_score < float(params.min_blue_score):
        reasons.append("blue_shape")
    if outer_score < float(params.min_outer_score):
        reasons.append("outer_shape")
    if shape_score < float(params.min_shape_score):
        reasons.append("combined_shape")
    if blue_pixels < int(params.min_blue_pixels):
        reasons.append("blue_pixels_low")
    if int(params.max_blue_pixels) > 0 and blue_pixels > int(params.max_blue_pixels) and not signature_ok:
        reasons.append("blue_pixels_high")
    if outer_pixels < int(params.min_outer_pixels):
        reasons.append("outer_pixels_low")

    return PortalShapeColorHit(
        score=float(score),
        blue_score=float(blue_score),
        outer_score=float(outer_score),
        shape_score=float(shape_score),
        edge_score=float(edge_score),
        color_score=float(color_score),
        signature_score=float(signature_score),
        response_score=float(response_score),
        scale=float(prepared.scale),
        top_left=(x, y),
        size=(int(w), int(h)),
        template_name=prepared.name,
        blue_pixels=int(blue_pixels),
        outer_pixels=int(outer_pixels),
        template_blue_pixels=int(template_blue_pixels),
        template_outer_pixels=int(template_outer_pixels),
        accepted=not reasons,
        reject_reasons=reasons,
    )


def _mask_response(frame_mask: np.ndarray, template_mask: np.ndarray) -> np.ndarray:
    if int(np.count_nonzero(template_mask)) < 3:
        out_h = frame_mask.shape[0] - template_mask.shape[0] + 1
        out_w = frame_mask.shape[1] - template_mask.shape[1] + 1
        return np.zeros((max(1, out_h), max(1, out_w)), dtype=np.float32)
    frame_norm = frame_mask.astype(np.float32) / 255.0
    template_norm = template_mask.astype(np.float32) / 255.0
    response = cv2.matchTemplate(frame_norm, template_norm, cv2.TM_CCORR_NORMED)
    return np.nan_to_num(response, nan=-1.0, posinf=-1.0, neginf=-1.0)


def _color_response(frame: np.ndarray, template: np.ndarray, shape_mask: np.ndarray) -> np.ndarray:
    try:
        if int(np.count_nonzero(shape_mask)) >= 8:
            response = cv2.matchTemplate(_to_bgr(frame), template, cv2.TM_CCORR_NORMED, mask=shape_mask)
        else:
            response = cv2.matchTemplate(_to_bgr(frame), template, cv2.TM_CCOEFF_NORMED)
        return np.nan_to_num(response, nan=-1.0, posinf=-1.0, neginf=-1.0)
    except cv2.error:
        out_h = frame.shape[0] - template.shape[0] + 1
        out_w = frame.shape[1] - template.shape[1] + 1
        return np.zeros((max(1, out_h), max(1, out_w)), dtype=np.float32)


def _patch_color_score(frame_patch: np.ndarray, template: np.ndarray, shape_mask: np.ndarray) -> float:
    if frame_patch.shape[:2] != template.shape[:2] or frame_patch.size == 0:
        return 0.0
    mask = shape_mask > 0
    if int(np.count_nonzero(mask)) < 3:
        return 0.0
    patch_hsv = _to_hsv(frame_patch).astype(np.float32)
    template_hsv = _to_hsv(template).astype(np.float32)
    diff = np.abs(patch_hsv[mask] - template_hsv[mask])
    hue_diff = np.minimum(diff[:, 0], 180.0 - diff[:, 0]) / 90.0
    sat_diff = diff[:, 1] / 255.0
    val_diff = diff[:, 2] / 255.0
    distance = hue_diff * 0.45 + sat_diff * 0.25 + val_diff * 0.30
    return float(max(0.0, 1.0 - float(np.mean(distance))))


def _f1_score(patch_mask: np.ndarray, template_mask: np.ndarray) -> tuple[float, int, int]:
    if patch_mask.shape[:2] != template_mask.shape[:2]:
        return 0.0, 0, int(np.count_nonzero(template_mask))
    patch = patch_mask > 0
    template = template_mask > 0
    patch_pixels = int(np.count_nonzero(patch))
    template_pixels = int(np.count_nonzero(template))
    if patch_pixels <= 0 or template_pixels <= 0:
        return 0.0, patch_pixels, template_pixels
    intersection = int(np.count_nonzero(patch & template))
    precision = float(intersection) / float(max(1, patch_pixels))
    recall = float(intersection) / float(max(1, template_pixels))
    if precision + recall <= 0:
        return 0.0, patch_pixels, template_pixels
    return float(2.0 * precision * recall / (precision + recall)), patch_pixels, template_pixels


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


def _resize_image(image: np.ndarray, scale: float) -> np.ndarray:
    h, w = image.shape[:2]
    new_w = max(4, int(round(w * float(scale))))
    new_h = max(4, int(round(h * float(scale))))
    return cv2.resize(_to_bgr(image), (new_w, new_h), interpolation=cv2.INTER_AREA)


def _resize_mask(mask: np.ndarray, scale: float) -> np.ndarray:
    h, w = mask.shape[:2]
    new_w = max(4, int(round(w * float(scale))))
    new_h = max(4, int(round(h * float(scale))))
    return cv2.resize(mask, (new_w, new_h), interpolation=cv2.INTER_NEAREST)


def _to_bgr(image: np.ndarray) -> np.ndarray:
    if image.ndim == 2:
        return cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
    return image[:, :, :3]


def _to_hsv(image: np.ndarray) -> np.ndarray:
    return cv2.cvtColor(_to_bgr(image), cv2.COLOR_BGR2HSV)
