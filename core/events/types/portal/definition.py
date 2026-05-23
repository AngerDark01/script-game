from __future__ import annotations

from core.events.base.definition import EventDefinition

from .config import PortalEventConfig
from .handler import PortalEventHandler
from .minimap_detector import PortalMinimapDetector


class PortalEventDefinition(EventDefinition):
    event_type = "portal"
    display_name = "Portal"
    description = "Detect the portal minimap icon, localize it through wall registration, move near it, then interact."

    def default_config(self) -> dict:
        return PortalEventConfig().to_dict()

    def config_schema(self) -> dict:
        return {
            "enabled": {"type": "bool", "label": "enabled"},
            "priority": {"type": "int", "label": "priority", "min": 0, "max": 1000},
            "interaction": {"type": "choice", "label": "interaction", "choices": ["click", "key"]},
            "minimap_threshold": {"type": "float", "label": "minimap threshold", "min": 0.1, "max": 1.0},
            "stable_frames": {"type": "int", "label": "stable frames", "min": 1, "max": 10},
            "localization_cluster_radius": {"type": "int", "label": "cluster radius", "min": 20, "max": 300},
            "stable_variance": {"type": "float", "label": "stable variance", "min": 100.0, "max": 10000.0},
            "arrival_radius": {"type": "int", "label": "arrival radius", "min": 10, "max": 300},
            "retry_limit": {"type": "int", "label": "retry limit", "min": 0, "max": 5},
        }

    def create_detector(self, config):
        return PortalMinimapDetector(PortalEventConfig.from_dict(config))

    def create_handler(self, config):
        return PortalEventHandler(PortalEventConfig.from_dict(config))
