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
            "detector_mode": {
                "type": "choice",
                "label": "minimap detector mode",
                "choices": ["feature_then_template", "feature", "shape_color", "template"],
                "default": "feature_then_template",
            },
            "minimap_threshold": {"type": "float", "label": "minimap threshold", "min": 0.1, "max": 1.0},
            "max_candidates": {"type": "int", "label": "max candidates per frame", "min": 1, "max": 12, "default": 2},
            "min_blue_ratio": {"type": "float", "label": "min blue ratio", "min": 0.0, "max": 1.0, "step": 0.01, "default": 0.08},
            "feature_detector_enabled": {"type": "bool", "label": "legacy feature detector switch", "editable": False},
            "feature_hue_min": {"type": "int", "label": "feature hue min", "min": 0, "max": 179, "default": 82},
            "feature_hue_max": {"type": "int", "label": "feature hue max", "min": 0, "max": 179, "default": 136},
            "feature_sat_min": {"type": "int", "label": "feature saturation min", "min": 0, "max": 255, "default": 55},
            "feature_val_min": {"type": "int", "label": "feature value min", "min": 0, "max": 255, "default": 95},
            "feature_min_blue_pixels": {"type": "int", "label": "feature min blue pixels", "min": 1, "max": 2000, "default": 36},
            "feature_max_blue_pixels": {"type": "int", "label": "feature max blue pixels", "min": 0, "max": 5000, "default": 420},
            "shape_outer_sat_max": {"type": "int", "label": "shape outer sat max", "min": 0, "max": 255, "default": 115},
            "shape_outer_val_min": {"type": "int", "label": "shape outer value min", "min": 0, "max": 255, "default": 105},
            "shape_min_blue_score": {"type": "float", "label": "shape min blue score", "min": 0.0, "max": 1.0, "step": 0.01, "default": 0.28},
            "shape_min_outer_score": {"type": "float", "label": "shape min outer score", "min": 0.0, "max": 1.0, "step": 0.01, "default": 0.18},
            "shape_min_shape_score": {"type": "float", "label": "shape min combined score", "min": 0.0, "max": 1.0, "step": 0.01, "default": 0.30},
            "shape_min_outer_pixels": {"type": "int", "label": "shape min outer pixels", "min": 0, "max": 2000, "default": 14},
            "shape_signature_min_outer_score": {"type": "float", "label": "signature min outer score", "min": 0.0, "max": 1.0, "step": 0.01, "default": 0.45},
            "shape_signature_min_edge_score": {"type": "float", "label": "signature min edge score", "min": 0.0, "max": 1.0, "step": 0.01, "default": 0.40},
            "shape_signature_min_color_score": {"type": "float", "label": "signature min color score", "min": 0.0, "max": 1.0, "step": 0.01, "default": 0.82},
            "shape_signature_score_scale": {"type": "float", "label": "signature score scale", "min": 0.1, "max": 3.0, "step": 0.05, "default": 1.30},
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
