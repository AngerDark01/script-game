from __future__ import annotations

from .debug import event_log


class EventMonitor:
    def __init__(self, registry):
        self.registry = registry
        self._detectors = {}

    def detect(self, tick, config) -> list:
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
            observations.extend(detector.detect(tick, event_config))
        return observations
