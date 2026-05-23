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
            "arrival_radius": {"type": "int", "label": "arrival_radius (approach)", "min": 10, "max": 300, "step": 2, "default": 80},
            "interact_radius": {"type": "int", "label": "interact_radius (press D distance)", "min": 1, "max": 120, "step": 1, "default": 36},
            "portal_point_click_wait_ms": {"type": "int", "label": "portal point click wait ms", "min": 0, "max": 2000, "step": 50, "default": 350},
            "cooldown_ms": {"type": "int", "label": "cooldown_ms (position)", "min": 0, "max": 600000, "step": 1000, "default": 120000},
            "type_cooldown_ms": {"type": "int", "label": "type_cooldown_ms (after teleport)", "min": 0, "max": 60000, "step": 500, "default": 10000},
            "retry_limit": {"type": "int", "label": "retry limit", "min": 0, "max": 5},
        }

    def create_detector(self, config):
        return PortalMinimapDetector(PortalEventConfig.from_dict(config))

    def create_handler(self, config):
        return PortalEventHandler(PortalEventConfig.from_dict(config))
