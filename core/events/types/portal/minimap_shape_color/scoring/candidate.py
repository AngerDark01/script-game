from __future__ import annotations

import numpy as np

from ..models import PortalShapeColorHit, PortalShapeColorParams, PreparedShapeColorTemplate
from .color import patch_color_score
from .overlap import f1_score


def evaluate_shape_color_candidate(
    frame: np.ndarray,
    frame_blue: np.ndarray,
    frame_outer: np.ndarray,
    frame_shape: np.ndarray,
    frame_edges: np.ndarray,
    prepared: PreparedShapeColorTemplate,
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

    blue_score, blue_pixels, template_blue_pixels = f1_score(blue_patch, prepared.blue_mask)
    outer_score, outer_pixels, template_outer_pixels = f1_score(outer_patch, prepared.outer_mask)
    shape_score, _, _ = f1_score(shape_patch, prepared.shape_mask)
    edge_score, _, _ = f1_score(edge_patch, prepared.edge_mask)
    color_score = patch_color_score(frame_patch, prepared.image, prepared.shape_mask)
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
