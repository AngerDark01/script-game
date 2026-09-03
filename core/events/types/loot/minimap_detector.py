from __future__ import annotations

from core.events.base.detector import EventDetector
from core.events.debug import event_log
from core.events.models import EventDetection

from .assets import LOOT_MINIMAP_TEMPLATES, LOOT_PLAYER_MARKER_EXCLUDE_TEMPLATES
from .config import LootEventConfig
from .diagnostics import LootDiagnosticCapture
from .detection import clusters_to_detections, detect_loot_blobs, detect_loot_presence, load_loot_templates
from .detection.feature_match import FeatureLootMatcher
from .detection.templates import prepare_scaled_templates
from .perception import AsyncLootPerception


class LootMinimapDetector(EventDetector):
    event_type = "loot"

    def __init__(self, config):
        self.config = config if isinstance(config, LootEventConfig) else LootEventConfig.from_dict(config)
        self.templates = load_loot_templates(LOOT_MINIMAP_TEMPLATES)
        self.prepared_templates = prepare_scaled_templates(self.templates, self.config.scale_values())
        self.feature_prepared_templates = prepare_scaled_templates(self.templates, self.config.feature_match_scale_values())
        self.feature_matcher = FeatureLootMatcher(self.feature_prepared_templates, self.config)
        self.exclusion_templates = prepare_scaled_templates(
            load_loot_templates(LOOT_PLAYER_MARKER_EXCLUDE_TEMPLATES),
            self.config.scale_values(),
        )
        self.async_perception = AsyncLootPerception(self.event_type)
        self._cached_detections: list[EventDetection] = []
        self._last_detect_ms: int = -1
        self._presence_streak: int = 0
        self._last_log_ms = 0
        self._diagnostics = LootDiagnosticCapture()
        event_log(
            "loot minimap detector ready",
            templates=len(self.templates),
            prepared_templates=len(self.prepared_templates),
            exclusion_templates=len(self.exclusion_templates),
            threshold=float(self.config.weighted_threshold),
            mode=self.config.detector_mode,
            feature_scales=self.config.feature_match_scales,
        )

    def detect(self, tick, config) -> list[EventDetection]:
        next_config = config if isinstance(config, LootEventConfig) else LootEventConfig.from_dict(config)
        self._refresh_prepared_templates_if_needed(next_config)
        self.config = next_config
        if tick.raw_minimap_frame is None or not self.prepared_templates:
            self._log_skipped(tick)
            return []

        seed_bboxes = detect_loot_presence(tick.raw_minimap_frame, self.config, self.exclusion_templates)
        if self._uses_async_feature_match():
            return self._detect_async_feature_match(tick, seed_bboxes)
        if not seed_bboxes:
            self._presence_streak = 0
            self._cached_detections = []
            self._last_detect_ms = -1
            return []

        self._presence_streak += 1
        confirm_frames = max(1, int(getattr(self.config, "presence_confirm_frames", 2) or 2))
        if self._presence_streak < confirm_frames:
            if self._should_log(tick.now_ms, 1200):
                event_log(
                    "loot presence pending",
                    seeds=len(seed_bboxes),
                    streak=int(self._presence_streak),
                    confirm_frames=int(confirm_frames),
                )
            return self._retime_cached_detections(tick.now_ms) if self._cached_detections else []

        if self._should_reuse_cached_detections(tick.now_ms):
            return self._retime_cached_detections(tick.now_ms)

        clusters = self._detect_clusters(tick.raw_minimap_frame, seed_bboxes)
        detections = clusters_to_detections(
            self.event_type,
            clusters,
            tick.now_ms,
            pickup_radius=int(self.config.pickup_radius),
            source=self._detection_source(),
        )
        self._last_detect_ms = int(tick.now_ms)
        self._cached_detections = list(detections)
        if detections and self._should_log(tick.now_ms, 750):
            event_log(
                "loot detections",
                count=len(detections),
                best=max(float(item.confidence) for item in detections),
                centers=[item.local_minimap_pos for item in detections],
            )
        self._diagnostics.maybe_capture(
            frame=tick.raw_minimap_frame,
            detections=detections,
            config=self.config,
            templates=self.prepared_templates,
            exclusion_templates=self.exclusion_templates,
            seed_bboxes=seed_bboxes,
            now_ms=int(tick.now_ms),
        )
        return detections

    def _refresh_prepared_templates_if_needed(self, config: LootEventConfig) -> None:
        if (
            str(config.scales) == str(self.config.scales)
            and str(config.feature_match_scales) == str(self.config.feature_match_scales)
            and bool(config.masked_color_match_enabled) == bool(self.config.masked_color_match_enabled)
        ):
            return
        self.prepared_templates = prepare_scaled_templates(self.templates, config.scale_values())
        self.feature_prepared_templates = prepare_scaled_templates(self.templates, config.feature_match_scale_values())
        self.feature_matcher = FeatureLootMatcher(self.feature_prepared_templates, config)
        self.exclusion_templates = prepare_scaled_templates(
            load_loot_templates(LOOT_PLAYER_MARKER_EXCLUDE_TEMPLATES),
            config.scale_values(),
        )
        self.async_perception.clear()
        self._cached_detections = []
        self._last_detect_ms = -1
        self._presence_streak = 0

    def _detect_async_feature_match(self, tick, seed_bboxes) -> list[EventDetection]:
        self.async_perception.update_visibility(
            seed_bboxes,
            getattr(tick, "frame_registration", None),
            self.config,
            int(tick.now_ms),
        )
        if not seed_bboxes:
            self._presence_streak = 0
            return []

        self._presence_streak += 1
        confirm_frames = max(1, int(getattr(self.config, "presence_confirm_frames", 2) or 2))
        if self._presence_streak >= confirm_frames:
            submitted = self.async_perception.maybe_submit(
                frame=tick.raw_minimap_frame,
                registration=getattr(tick, "frame_registration", None),
                seeds=seed_bboxes,
                matcher=self.feature_matcher,
                config=self.config,
                now_ms=int(tick.now_ms),
            )
            if submitted and self._should_log(tick.now_ms, 750):
                event_log("loot async perception submitted", seeds=len(seed_bboxes))
        elif self._should_log(tick.now_ms, 1200):
            event_log(
                "loot async presence pending",
                seeds=len(seed_bboxes),
                streak=int(self._presence_streak),
                confirm_frames=int(confirm_frames),
            )

        detections = self.async_perception.detections(
            getattr(tick, "frame_registration", None),
            self.config,
            int(tick.now_ms),
        )
        if detections and self._should_log(tick.now_ms, 750):
            event_log(
                "loot async detections",
                count=len(detections),
                best=max(float(item.confidence) for item in detections),
                centers=[item.local_minimap_pos for item in detections],
            )
        return detections

    def _detect_clusters(self, frame, seed_bboxes):
        if self._uses_feature_match():
            return self.feature_matcher.detect(frame, seed_bboxes)
        return detect_loot_blobs(
            frame,
            self.prepared_templates,
            self.config,
            self.exclusion_templates,
            seed_bboxes=seed_bboxes,
        )

    def _uses_async_feature_match(self) -> bool:
        return str(getattr(self.config, "detector_mode", "")).strip().lower() == "async_feature_match"

    def _uses_feature_match(self) -> bool:
        return str(getattr(self.config, "detector_mode", "")).strip().lower() == "feature_match"

    def _detection_source(self) -> str:
        if self._uses_feature_match():
            return "minimap_feature_match"
        return "minimap_weighted_blob"

    def _should_reuse_cached_detections(self, now_ms: int) -> bool:
        interval_ms = int(getattr(self.config, "detection_interval_ms", 0) or 0)
        if interval_ms <= 0 or self._last_detect_ms < 0:
            return False
        if int(now_ms) - int(self._last_detect_ms) >= interval_ms:
            return False
        return bool(getattr(self.config, "reuse_previous_detections", True))

    def _retime_cached_detections(self, now_ms: int) -> list[EventDetection]:
        return [
            EventDetection(
                event_type=item.event_type,
                confidence=item.confidence,
                detected_at_ms=int(now_ms),
                local_minimap_pos=item.local_minimap_pos,
                source=item.source,
                metadata=dict(item.metadata or {}),
            )
            for item in self._cached_detections
        ]

    def _log_skipped(self, tick) -> None:
        if self._should_log(int(getattr(tick, "now_ms", 0) or 0), 3000):
            event_log(
                "loot detector skipped",
                has_frame=tick.raw_minimap_frame is not None,
                templates=len(self.prepared_templates),
            )

    def _should_log(self, now_ms: int, interval_ms: int) -> bool:
        if now_ms - self._last_log_ms < interval_ms:
            return False
        self._last_log_ms = int(now_ms)
        return True
