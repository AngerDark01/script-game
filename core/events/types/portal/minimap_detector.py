from __future__ import annotations

import cv2
import numpy as np

from core.events.base.detector import EventDetector
from core.events.debug import event_log
from core.events.detectors.template_matcher import load_template, match_templates
from core.events.models import EventDetection

from .assets import PORTAL_MINIMAP_TEMPLATES
from .config import PortalEventConfig
from .minimap_feature_matcher import build_feature_templates, match_portal_features, portal_blue_mask
from .minimap_shape_color_matcher import PortalShapeColorParams, match_portal_shape_color


class PortalMinimapDetector(EventDetector):
    event_type = "portal"

    def __init__(self, config):
        self.config = config
        self.templates = [load_template(path) for path in PORTAL_MINIMAP_TEMPLATES if path.exists()]
        self.feature_templates = []
        self._feature_signature = None
        self.scales = [0.75, 0.85, 1.0, 1.15, 1.3]
        self._last_log_ms = 0
        self._refresh_feature_templates()
        event_log(
            "portal minimap detector ready",
            templates=len(self.templates),
            feature_templates=len(self.feature_templates),
            threshold=float(self.config.minimap_threshold),
            mode=self._detector_mode(),
        )

    def detect(self, tick, config) -> list[EventDetection]:
        self.config = config if isinstance(config, PortalEventConfig) else PortalEventConfig.from_dict(config)
        self._refresh_feature_templates()
        if tick.raw_minimap_frame is None or not self.templates:
            if tick.now_ms - self._last_log_ms >= 3000:
                self._last_log_ms = int(tick.now_ms)
                event_log(
                    "portal minimap detector skipped",
                    frame=tick.raw_minimap_frame is not None,
                    templates=len(self.templates),
                    feature_templates=len(self.feature_templates),
                )
            return []

        mode = self._detector_mode()
        hits = []
        hit_source = mode
        if mode in {"feature", "feature_then_template"}:
            hits = self._detect_feature_hits(tick.raw_minimap_frame)
            hit_source = "feature"
        elif mode == "shape_color":
            hits = self._detect_shape_color_hits(tick.raw_minimap_frame, tick.now_ms)
            hit_source = "shape_color"

        if not hits and mode in {"template", "feature_then_template"}:
            hits = match_templates(
                tick.raw_minimap_frame,
                self.templates,
                self.scales,
                top_k=max(2, int(getattr(self.config, "max_candidates", 2)) * 3),
                threshold=float(self.config.minimap_threshold),
            )
            hit_source = "template" if mode == "template" else "template_fallback"
        if not hits and tick.now_ms - self._last_log_ms >= 1000:
            self._last_log_ms = int(tick.now_ms)
            try:
                feature_mask = portal_blue_mask(
                    tick.raw_minimap_frame,
                    hue_min=int(getattr(self.config, "feature_hue_min", 82)),
                    hue_max=int(getattr(self.config, "feature_hue_max", 136)),
                    sat_min=int(getattr(self.config, "feature_sat_min", 55)),
                    val_min=int(getattr(self.config, "feature_val_min", 95)),
                )
                feature_blue_pixels = int(np.count_nonzero(feature_mask))
            except Exception:
                feature_blue_pixels = -1
            event_log(
                "portal minimap no hits",
                source=mode,
                templates=len(self.templates),
                feature_templates=len(self.feature_templates),
                threshold=float(getattr(self.config, "minimap_threshold", 0.74)),
                feature_enabled=mode in {"feature", "feature_then_template"},
                feature_blue_pixels=feature_blue_pixels,
                feature_sat_min=int(getattr(self.config, "feature_sat_min", 55)),
                feature_val_min=int(getattr(self.config, "feature_val_min", 95)),
                min_blue_pixels=int(getattr(self.config, "feature_min_blue_pixels", 36)),
                max_blue_pixels=int(getattr(self.config, "feature_max_blue_pixels", 420)),
                shape_outer_sat_max=int(getattr(self.config, "shape_outer_sat_max", 115)),
                shape_outer_val_min=int(getattr(self.config, "shape_outer_val_min", 105)),
            )
        detections: list[EventDetection] = []
        for hit in hits:
            if len(detections) >= int(getattr(self.config, "max_candidates", 2)):
                break
            color_check = _portal_color_check(tick.raw_minimap_frame, hit, float(getattr(self.config, "min_blue_ratio", 0.08)))
            if not color_check["accepted"]:
                if tick.now_ms - self._last_log_ms >= 750:
                    self._last_log_ms = int(tick.now_ms)
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
                continue
            detections.append(
                EventDetection(
                    event_type=self.event_type,
                    local_minimap_pos=hit.center,
                    confidence=float(hit.score),
                    detected_at_ms=int(tick.now_ms),
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
            )
        if hits and tick.now_ms - self._last_log_ms >= 750:
            self._last_log_ms = int(tick.now_ms)
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
        return detections

    def _detector_mode(self) -> str:
        mode = str(getattr(self.config, "detector_mode", "") or "").strip().lower()
        if mode in {"template", "feature", "feature_then_template", "shape_color"}:
            return mode
        if bool(getattr(self.config, "feature_detector_enabled", True)):
            return "feature_then_template"
        return "template"

    def _refresh_feature_templates(self) -> None:
        signature = (
            int(getattr(self.config, "feature_hue_min", 82)),
            int(getattr(self.config, "feature_hue_max", 136)),
            int(getattr(self.config, "feature_sat_min", 55)),
            int(getattr(self.config, "feature_val_min", 95)),
        )
        if signature == self._feature_signature:
            return
        self._feature_signature = signature
        self.feature_templates = build_feature_templates(
            self.templates,
            hue_min=signature[0],
            hue_max=signature[1],
            sat_min=signature[2],
            val_min=signature[3],
        )

    def _detect_feature_hits(self, frame):
        if not self.feature_templates:
            return []
        return match_portal_features(
            frame,
            self.feature_templates,
            self.scales,
            top_k=max(2, int(getattr(self.config, "max_candidates", 2)) * 3),
            threshold=float(getattr(self.config, "minimap_threshold", 0.74)),
            hue_min=int(getattr(self.config, "feature_hue_min", 82)),
            hue_max=int(getattr(self.config, "feature_hue_max", 136)),
            sat_min=int(getattr(self.config, "feature_sat_min", 55)),
            val_min=int(getattr(self.config, "feature_val_min", 95)),
            min_blue_pixels=int(getattr(self.config, "feature_min_blue_pixels", 36)),
            max_blue_pixels=int(getattr(self.config, "feature_max_blue_pixels", 420)),
        )

    def _detect_shape_color_hits(self, frame, now_ms: int):
        params = PortalShapeColorParams(
            threshold=float(getattr(self.config, "minimap_threshold", 0.74)),
            hue_min=int(getattr(self.config, "feature_hue_min", 82)),
            hue_max=int(getattr(self.config, "feature_hue_max", 136)),
            sat_min=int(getattr(self.config, "feature_sat_min", 55)),
            val_min=int(getattr(self.config, "feature_val_min", 95)),
            outer_sat_max=int(getattr(self.config, "shape_outer_sat_max", 115)),
            outer_val_min=int(getattr(self.config, "shape_outer_val_min", 105)),
            min_blue_pixels=int(getattr(self.config, "feature_min_blue_pixels", 36)),
            max_blue_pixels=int(getattr(self.config, "feature_max_blue_pixels", 420)),
            min_outer_pixels=int(getattr(self.config, "shape_min_outer_pixels", 14)),
            min_blue_score=float(getattr(self.config, "shape_min_blue_score", 0.28)),
            min_outer_score=float(getattr(self.config, "shape_min_outer_score", 0.18)),
            min_shape_score=float(getattr(self.config, "shape_min_shape_score", 0.30)),
            signature_min_outer_score=float(getattr(self.config, "shape_signature_min_outer_score", 0.45)),
            signature_min_edge_score=float(getattr(self.config, "shape_signature_min_edge_score", 0.40)),
            signature_min_color_score=float(getattr(self.config, "shape_signature_min_color_score", 0.82)),
            signature_score_scale=float(getattr(self.config, "shape_signature_score_scale", 1.30)),
        )
        hits, _debug = match_portal_shape_color(
            frame,
            self.templates,
            self.scales,
            top_k=max(2, int(getattr(self.config, "max_candidates", 2)) * 3),
            params=params,
        )
        accepted = [hit for hit in hits if hit.accepted]
        if hits and not accepted and now_ms - self._last_log_ms >= 1000:
            self._last_log_ms = int(now_ms)
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
        return accepted


def _portal_color_check(frame, hit, min_blue_ratio: float) -> dict:
    x, y = hit.top_left
    w, h = hit.size
    pad = max(2, int(round(min(w, h) * 0.15)))
    left = max(0, int(x) - pad)
    top = max(0, int(y) - pad)
    right = min(frame.shape[1], int(x + w) + pad)
    bottom = min(frame.shape[0], int(y + h) + pad)
    patch = frame[top:bottom, left:right]
    if patch.size == 0:
        return {"accepted": False, "blue_ratio": 0.0, "blue_pixels": 0}

    if patch.ndim == 3:
        hsv = cv2.cvtColor(patch, cv2.COLOR_BGR2HSV)
    else:
        hsv = cv2.cvtColor(cv2.cvtColor(patch, cv2.COLOR_GRAY2BGR), cv2.COLOR_BGR2HSV)

    blue_mask = (
        (hsv[:, :, 0] >= 82)
        & (hsv[:, :, 0] <= 136)
        & (hsv[:, :, 1] >= 35)
        & (hsv[:, :, 2] >= 70)
    )
    blue_pixels = int(np.count_nonzero(blue_mask))
    area = int(patch.shape[0] * patch.shape[1])
    blue_ratio = float(blue_pixels / max(1, area))
    return {
        "accepted": bool(blue_ratio >= float(min_blue_ratio) and blue_pixels >= 18),
        "blue_ratio": blue_ratio,
        "blue_pixels": blue_pixels,
    }
