from __future__ import annotations

import math

from core.events.models import EventDetection

from ..minimap_hit_filter import portal_color_check
from .diagnostics import maybe_log_hit_rejected


def collect_event_detections(detector, frame, hits, hit_source: str, now_ms: int) -> list[EventDetection]:
    detections: list[EventDetection] = []
    max_candidates = int(getattr(detector.config, "max_candidates", 2))
    min_blue_ratio = float(getattr(detector.config, "min_blue_ratio", 0.08))
    nms_radius = max(0.0, float(getattr(detector.config, "minimap_nms_radius", 0) or 0))

    for hit in hits:
        if len(detections) >= max_candidates:
            break
        color_check = portal_color_check(frame, hit, min_blue_ratio)
        if not color_check["accepted"]:
            maybe_log_hit_rejected(detector, hit, color_check, hit_source, now_ms)
            continue
        if _near_existing_detection(hit.center, detections, nms_radius):
            continue
        detections.append(_hit_to_detection(detector.event_type, hit, color_check, hit_source, now_ms))
    return detections


def _near_existing_detection(center: tuple[int, int], detections: list[EventDetection], radius: float) -> bool:
    if radius <= 0:
        return False
    center_x, center_y = center
    for detection in detections:
        kept_x, kept_y = detection.local_minimap_pos
        if math.hypot(float(center_x) - float(kept_x), float(center_y) - float(kept_y)) <= radius:
            return True
    return False


def _hit_to_detection(event_type: str, hit, color_check: dict, hit_source: str, now_ms: int) -> EventDetection:
    return EventDetection(
        event_type=event_type,
        local_minimap_pos=hit.center,
        confidence=float(hit.score),
        detected_at_ms=int(now_ms),
        source=f"minimap_{hit_source}",
        metadata={
            "template": hit.template_name,
            "scale": hit.scale,
            "detector": hit_source,
            "accepted": bool(getattr(hit, "accepted", True)),
            "reject_reasons": list(getattr(hit, "reject_reasons", [])),
            "blue_score": float(getattr(hit, "blue_score", 0.0)),
            "outer_score": float(getattr(hit, "outer_score", 0.0)),
            "shape_score": float(getattr(hit, "shape_score", 0.0)),
            "color_score": float(getattr(hit, "color_score", 0.0)),
            "signature_score": float(getattr(hit, "signature_score", 0.0)),
            "response_score": float(getattr(hit, "response_score", hit.score)),
            "gray_score": float(getattr(hit, "gray_score", 0.0)),
            "edge_score": float(getattr(hit, "edge_score", 0.0)),
            "mask_score": float(getattr(hit, "mask_score", hit.score)),
            "density_score": float(getattr(hit, "density_score", 0.0)),
            "feature_blue_pixels": int(getattr(hit, "blue_pixels", 0)),
            "feature_template_pixels": int(getattr(hit, "template_pixels", getattr(hit, "template_blue_pixels", 0))),
            "blue_ratio": color_check["blue_ratio"],
            "blue_pixels": color_check["blue_pixels"],
            "bbox": [hit.top_left[0], hit.top_left[1], hit.size[0], hit.size[1]],
        },
    )
