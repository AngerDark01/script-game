from __future__ import annotations

from core.events.detectors.template_matcher import match_templates

from ..minimap_feature_matcher import build_feature_templates, match_portal_features
from ..minimap_shape_color import PortalShapeColorParams, match_portal_shape_color


def detector_mode(config) -> str:
    mode = str(getattr(config, "detector_mode", "") or "").strip().lower()
    if mode in {"template", "feature", "feature_then_template", "shape_color"}:
        return mode
    if bool(getattr(config, "feature_detector_enabled", True)):
        return "feature_then_template"
    return "template"


def feature_signature(config) -> tuple[int, int, int, int]:
    return (
        int(getattr(config, "feature_hue_min", 82)),
        int(getattr(config, "feature_hue_max", 136)),
        int(getattr(config, "feature_sat_min", 55)),
        int(getattr(config, "feature_val_min", 95)),
    )


def refresh_feature_templates(templates, config, current_signature, current_templates):
    signature = feature_signature(config)
    if signature == current_signature:
        return current_signature, current_templates
    feature_templates = build_feature_templates(
        templates,
        hue_min=signature[0],
        hue_max=signature[1],
        sat_min=signature[2],
        val_min=signature[3],
    )
    return signature, feature_templates


def top_k_candidates(config) -> int:
    return max(2, int(getattr(config, "max_candidates", 2)) * 3)


def detect_feature_hits(config, frame, feature_templates, scales):
    if not feature_templates:
        return []
    return match_portal_features(
        frame,
        feature_templates,
        scales,
        top_k=top_k_candidates(config),
        threshold=float(getattr(config, "minimap_threshold", 0.74)),
        hue_min=int(getattr(config, "feature_hue_min", 82)),
        hue_max=int(getattr(config, "feature_hue_max", 136)),
        sat_min=int(getattr(config, "feature_sat_min", 55)),
        val_min=int(getattr(config, "feature_val_min", 95)),
        min_blue_pixels=int(getattr(config, "feature_min_blue_pixels", 36)),
        max_blue_pixels=int(getattr(config, "feature_max_blue_pixels", 420)),
    )


def detect_template_hits(config, frame, templates, scales):
    return match_templates(
        frame,
        templates,
        scales,
        top_k=top_k_candidates(config),
        threshold=float(getattr(config, "minimap_threshold", 0.74)),
    )


def shape_color_params(config) -> PortalShapeColorParams:
    return PortalShapeColorParams(
        threshold=float(getattr(config, "minimap_threshold", 0.74)),
        hue_min=int(getattr(config, "feature_hue_min", 82)),
        hue_max=int(getattr(config, "feature_hue_max", 136)),
        sat_min=int(getattr(config, "feature_sat_min", 55)),
        val_min=int(getattr(config, "feature_val_min", 95)),
        outer_sat_max=int(getattr(config, "shape_outer_sat_max", 115)),
        outer_val_min=int(getattr(config, "shape_outer_val_min", 105)),
        min_blue_pixels=int(getattr(config, "feature_min_blue_pixels", 36)),
        max_blue_pixels=int(getattr(config, "feature_max_blue_pixels", 420)),
        min_outer_pixels=int(getattr(config, "shape_min_outer_pixels", 14)),
        min_blue_score=float(getattr(config, "shape_min_blue_score", 0.28)),
        min_outer_score=float(getattr(config, "shape_min_outer_score", 0.18)),
        min_shape_score=float(getattr(config, "shape_min_shape_score", 0.30)),
        signature_min_outer_score=float(getattr(config, "shape_signature_min_outer_score", 0.45)),
        signature_min_edge_score=float(getattr(config, "shape_signature_min_edge_score", 0.40)),
        signature_min_color_score=float(getattr(config, "shape_signature_min_color_score", 0.82)),
        signature_score_scale=float(getattr(config, "shape_signature_score_scale", 1.30)),
    )


def detect_shape_color_hits(config, frame, templates, scales):
    hits, _debug = match_portal_shape_color(
        frame,
        templates,
        scales,
        top_k=top_k_candidates(config),
        params=shape_color_params(config),
    )
    accepted = [hit for hit in hits if hit.accepted]
    return accepted, hits
