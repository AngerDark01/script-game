from __future__ import annotations

from core.events.base.detector import EventDetector
from core.events.debug import event_log
from core.events.detectors.template_matcher import load_template
from core.events.models import EventDetection

from .assets import PORTAL_MINIMAP_TEMPLATES
from .config import PortalEventConfig
from .minimap_hit_filter import portal_color_check
from .minimap_detection import (
    collect_event_detections,
    detect_feature_hits,
    detect_shape_color_hits,
    detect_template_hits,
    detector_mode,
    maybe_log_hits_summary,
    maybe_log_no_hits,
    maybe_log_shape_color_rejected,
    maybe_log_skipped,
    refresh_feature_templates,
)


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
            maybe_log_skipped(self, tick)
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
            hits = self._detect_template_hits(tick.raw_minimap_frame)
            hit_source = "template" if mode == "template" else "template_fallback"
        if not hits and tick.now_ms - self._last_log_ms >= 1000:
            maybe_log_no_hits(self, tick.raw_minimap_frame, tick.now_ms, mode)
        detections = collect_event_detections(self, tick.raw_minimap_frame, hits, hit_source, tick.now_ms)
        maybe_log_hits_summary(self, hits, detections, hit_source, mode, tick.now_ms)
        return detections

    def _detector_mode(self) -> str:
        return detector_mode(self.config)

    def _refresh_feature_templates(self) -> None:
        self._feature_signature, self.feature_templates = refresh_feature_templates(
            self.templates,
            self.config,
            self._feature_signature,
            self.feature_templates,
        )

    def _detect_feature_hits(self, frame):
        return detect_feature_hits(
            self.config,
            frame,
            self.feature_templates,
            self.scales,
        )

    def _detect_template_hits(self, frame):
        return detect_template_hits(self.config, frame, self.templates, self.scales)

    def _detect_shape_color_hits(self, frame, now_ms: int):
        accepted, hits = detect_shape_color_hits(self.config, frame, self.templates, self.scales)
        if hits and not accepted:
            maybe_log_shape_color_rejected(self, hits, now_ms)
        return accepted
