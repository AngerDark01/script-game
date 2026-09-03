from __future__ import annotations

import numpy as np

from core.events.debug import event_log

from ..minimap_feature_matcher import portal_blue_mask


def _can_log(detector, now_ms: int, interval_ms: int) -> bool:
    if int(now_ms) - int(detector._last_log_ms) < int(interval_ms):
        return False
    detector._last_log_ms = int(now_ms)
    return True


def maybe_log_skipped(detector, tick) -> None:
    if not _can_log(detector, tick.now_ms, 3000):
        return
    event_log(
        "portal minimap detector skipped",
        frame=tick.raw_minimap_frame is not None,
        templates=len(detector.templates),
        feature_templates=len(detector.feature_templates),
    )


def maybe_log_no_hits(detector, frame, now_ms: int, mode: str) -> None:
    if not _can_log(detector, now_ms, 1000):
        return
    try:
        feature_mask = portal_blue_mask(
            frame,
            hue_min=int(getattr(detector.config, "feature_hue_min", 82)),
            hue_max=int(getattr(detector.config, "feature_hue_max", 136)),
            sat_min=int(getattr(detector.config, "feature_sat_min", 55)),
            val_min=int(getattr(detector.config, "feature_val_min", 95)),
        )
        feature_blue_pixels = int(np.count_nonzero(feature_mask))
    except Exception:
        feature_blue_pixels = -1
    event_log(
        "portal minimap no hits",
        source=mode,
        templates=len(detector.templates),
        feature_templates=len(detector.feature_templates),
        threshold=float(getattr(detector.config, "minimap_threshold", 0.74)),
        feature_enabled=mode in {"feature", "feature_then_template"},
        feature_blue_pixels=feature_blue_pixels,
        feature_sat_min=int(getattr(detector.config, "feature_sat_min", 55)),
        feature_val_min=int(getattr(detector.config, "feature_val_min", 95)),
        min_blue_pixels=int(getattr(detector.config, "feature_min_blue_pixels", 36)),
        max_blue_pixels=int(getattr(detector.config, "feature_max_blue_pixels", 420)),
        shape_outer_sat_max=int(getattr(detector.config, "shape_outer_sat_max", 115)),
        shape_outer_val_min=int(getattr(detector.config, "shape_outer_val_min", 105)),
    )


def maybe_log_hit_rejected(detector, hit, color_check: dict, hit_source: str, now_ms: int) -> None:
    if not _can_log(detector, now_ms, 750):
        return
    event_log(
        "portal minimap hit rejected",
        score=float(hit.score),
        center=hit.center,
        template=hit.template_name,
        scale=float(hit.scale),
        source=hit_source,
        blue_ratio=float(color_check["blue_ratio"]),
        blue_pixels=int(color_check["blue_pixels"]),
    )


def maybe_log_hits_summary(detector, hits, detections, hit_source: str, mode: str, now_ms: int) -> None:
    if not hits or not _can_log(detector, now_ms, 750):
        return
    best = hits[0]
    event_log(
        "portal minimap hits",
        hits=len(hits),
        detections=len(detections),
        best_score=float(best.score),
        best_center=best.center,
        template=best.template_name,
        scale=float(best.scale),
        source=hit_source,
        mode=mode,
        mask_score=float(getattr(best, "mask_score", best.score)),
        density_score=float(getattr(best, "density_score", 0.0)),
        blue_score=float(getattr(best, "blue_score", 0.0)),
        outer_score=float(getattr(best, "outer_score", 0.0)),
        shape_score=float(getattr(best, "shape_score", 0.0)),
        edge_score=float(getattr(best, "edge_score", 0.0)),
        color_score=float(getattr(best, "color_score", 0.0)),
        signature_score=float(getattr(best, "signature_score", 0.0)),
        reject_reasons=",".join(getattr(best, "reject_reasons", [])),
    )


def maybe_log_shape_color_rejected(detector, hits, now_ms: int) -> None:
    if not hits or not _can_log(detector, now_ms, 1000):
        return
    best = hits[0]
    event_log(
        "portal minimap shape-color rejected",
        candidates=len(hits),
        best_score=float(best.score),
        best_center=best.center,
        template=best.template_name,
        scale=float(best.scale),
        blue_score=float(best.blue_score),
        outer_score=float(best.outer_score),
        shape_score=float(best.shape_score),
        edge_score=float(best.edge_score),
        color_score=float(best.color_score),
        signature_score=float(best.signature_score),
        blue_pixels=int(best.blue_pixels),
        outer_pixels=int(best.outer_pixels),
        reasons=",".join(best.reject_reasons),
    )
