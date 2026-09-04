from __future__ import annotations

from core.perception.models import TargetDetection

from .debug import event_log
from .perception_adapter import normalize_legacy_event_detections


class EventMonitor:
    def __init__(self, registry):
        self.registry = registry
        self._detectors = {}
        self.last_target_detections: list[TargetDetection] = []

    def detect(self, tick, config) -> list:
        self.last_target_detections = []
        if not getattr(config, "enabled", True):
            return []
        observations = []
        for definition in self.registry.enabled_definitions(config):
            event_config = config.event(definition.event_type)
            detector = self._detectors.get(definition.event_type)
            if detector is None:
                detector = definition.create_detector(event_config)
                self._detectors[definition.event_type] = detector
                event_log("detector initialized", event=definition.event_type, detector=detector.__class__.__name__)
            normalized, target_detections = normalize_legacy_event_detections(detector.detect(tick, event_config))
            self.last_target_detections.extend(target_detections)
            observations.extend(normalized)
        return observations
