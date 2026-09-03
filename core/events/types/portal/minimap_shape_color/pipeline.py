from __future__ import annotations

import cv2
import numpy as np

from core.events.detectors.template_matcher import TemplateSpec

from .masks import portal_blue_mask, portal_outer_mask, to_bgr
from .models import PortalShapeColorDebug, PortalShapeColorHit, PortalShapeColorParams
from .scoring import (
    combined_shape_color_response,
    evaluate_shape_color_candidate,
    response_hits,
)
from .templates import prepare_shape_color_template


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
    frame_edges = cv2.Canny(cv2.cvtColor(to_bgr(frame), cv2.COLOR_BGR2GRAY), 50, 150)

    hits: list[PortalShapeColorHit] = []
    threshold = float(params.threshold)
    collect = float(collect_threshold) if collect_threshold is not None else max(0.05, threshold - 0.22)

    for template in templates:
        for scale in scales:
            prepared = prepare_shape_color_template(template, float(scale), params)
            th, tw = prepared.shape_mask.shape[:2]
            if th >= frame.shape[0] or tw >= frame.shape[1]:
                continue
            if int(np.count_nonzero(prepared.blue_mask)) < 3:
                continue

            response = combined_shape_color_response(
                frame,
                frame_blue,
                frame_outer,
                frame_shape,
                frame_edges,
                prepared,
            )
            suppress = max(6, min(tw, th) // 2)
            for response_score, top_left in response_hits(response, max(1, int(top_k)) * 5, collect, suppress):
                hit = evaluate_shape_color_candidate(
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
