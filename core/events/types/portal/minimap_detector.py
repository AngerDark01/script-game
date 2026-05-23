from __future__ import annotations

import cv2
import numpy as np

from core.events.base.detector import EventDetector
from core.events.debug import event_log
from core.events.detectors.template_matcher import load_template, match_templates
from core.events.models import EventDetection

from .assets import PORTAL_MINIMAP_TEMPLATES
from .config import PortalEventConfig


class PortalMinimapDetector(EventDetector):
    event_type = "portal"

    def __init__(self, config):
        self.config = config
        self.templates = [load_template(path) for path in PORTAL_MINIMAP_TEMPLATES if path.exists()]
        self.scales = [0.75, 0.85, 1.0, 1.15, 1.3]
        self._last_log_ms = 0
        event_log(
            "portal minimap detector ready",
            templates=len(self.templates),
            threshold=float(self.config.minimap_threshold),
        )

    def detect(self, tick, config) -> list[EventDetection]:
        self.config = config if isinstance(config, PortalEventConfig) else PortalEventConfig.from_dict(config)
        if tick.raw_minimap_frame is None or not self.templates:
            if tick.now_ms - self._last_log_ms >= 3000:
                self._last_log_ms = int(tick.now_ms)
                event_log(
                    "portal minimap detector skipped",
                    frame=tick.raw_minimap_frame is not None,
                    templates=len(self.templates),
                )
            return []

        hits = match_templates(
            tick.raw_minimap_frame,
            self.templates,
            self.scales,
            top_k=max(2, int(getattr(self.config, "max_candidates", 2)) * 3),
            threshold=float(self.config.minimap_threshold),
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
                    source="minimap_template",
                    metadata={
                        "template": hit.template_name,
                        "scale": hit.scale,
                        "gray_score": hit.gray_score,
                        "edge_score": hit.edge_score,
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
            )
        return detections


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
