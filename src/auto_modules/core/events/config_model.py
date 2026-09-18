from __future__ import annotations

import copy
from dataclasses import dataclass, field


DEFAULT_EVENT_CONFIG = {
    "enabled": True,
    "profile": "default",
    "async_observer_interval_ms": 250,
    "hooks": {
        "instances": [],
    },
    "events": {
        "portal": {
            "enabled": True,
            "priority": 100,
            "navigation_approach_enabled": True,
            "interaction": "key",
            "detector_mode": "shape_color",
            "minimap_threshold": 0.74,
            "max_candidates": 2,
            "minimap_nms_radius": 28,
            "min_blue_ratio": 0.08,
            "feature_detector_enabled": True,
            "feature_hue_min": 82,
            "feature_hue_max": 136,
            "feature_sat_min": 55,
            "feature_val_min": 95,
            "feature_min_blue_pixels": 36,
            "feature_max_blue_pixels": 420,
            "shape_outer_sat_max": 115,
            "shape_outer_val_min": 105,
            "shape_min_blue_score": 0.28,
            "shape_min_outer_score": 0.18,
            "shape_min_shape_score": 0.30,
            "shape_min_outer_pixels": 14,
            "shape_signature_min_outer_score": 0.45,
            "shape_signature_min_edge_score": 0.40,
            "shape_signature_min_color_score": 0.82,
            "shape_signature_score_scale": 1.30,
            "stable_frames": 3,
            "localization_cluster_radius": 96,
            "stable_variance": 1600,
            "dedupe_radius": 96,
            "localization_max_samples": 12,
            "localization_cluster_ttl_ms": 12000,
            "localization_emit_interval_ms": 700,
            "memory_confirm_frames": 1,
            "target_update_mode": "limited_after_confirm",
            "target_update_max_drift": 18,
            "arrival_radius": 80,
            "interact_radius": 36,
            "retry_limit": 2,
            "cooldown_ms": 120000,
            "cooldown_radius": 260,
            "exit_complete_radius": 120,
            "type_cooldown_ms": 10000,
            "portal_point_click_wait_ms": 350,
            "post_interact_wait_ms": 800,
            "teleport_timeout_ms": 6000,
            "teleport_min_distance": 180,
            "environment_change_threshold": 0.18,
        },
        "loot": {
            "enabled": True,
            "priority": 60,
            "navigation_approach_enabled": True,
            "detector_mode": "async_feature_match",
            "weighted_threshold": 0.54,
            "collect_threshold": 0.28,
            "max_blobs_per_frame": 3,
            "top_k_per_template": 24,
            "detection_interval_ms": 450,
            "reuse_previous_detections": True,
            "presence_confirm_frames": 2,
            "masked_color_match_enabled": True,
            "roi_prefilter_enabled": True,
            "roi_min_area": 12,
            "roi_max_size": 150,
            "roi_expand": 48,
            "min_color_score": 0.12,
            "min_template_score": 0.25,
            "min_shape_score": 0.22,
            "template_weight": 0.46,
            "shape_weight": 0.42,
            "color_weight": 0.12,
            "player_marker_exclusion_enabled": True,
            "player_marker_template_threshold": 0.75,
            "player_marker_exact_template_threshold": 0.96,
            "player_marker_blue_ratio_threshold": 0.30,
            "player_marker_triangle_score_threshold": 0.54,
            "player_center_mask_enabled": True,
            "player_center_mask_overlay_enabled": True,
            "player_center_mask_radius": 28,
            "scales": "0.75,0.85,1.0,1.15,1.3",
            "feature_match_threshold": 0.64,
            "feature_match_collect_threshold": 0.38,
            "feature_match_top_k_per_template": 2,
            "feature_match_max_candidates": 5,
            "feature_match_search_padding": 48,
            "feature_match_scales": "0.75,0.85,1.0",
            "async_full_scan_interval_ms": 1000,
            "async_track_refresh_ms": 8000,
            "async_track_ttl_ms": 8000,
            "async_known_seed_radius": 72,
            "stable_frames": 2,
            "localization_cluster_radius": 72,
            "stable_variance": 2200,
            "dedupe_radius": 110,
            "localization_max_samples": 8,
            "localization_cluster_ttl_ms": 8000,
            "localization_emit_interval_ms": 150,
            "memory_confirm_frames": 1,
            "target_update_mode": "lock_after_confirm",
            "target_update_max_drift": 0,
            "arrival_radius": 90,
            "pickup_radius": 58,
            "pickup_key": "a",
            "post_pickup_wait_ms": 450,
            "absence_confirm_frames": 2,
            "absence_frame_ms": 250,
            "pickup_press_limit": 3,
            "retry_limit": 1,
            "cooldown_ms": 45000,
            "cooldown_radius": 180,
            "type_cooldown_ms": 0,
            "diagnostic_capture_enabled": False,
            "diagnostic_stage_dump_enabled": False,
            "diagnostic_capture_interval_ms": 1000,
            "diagnostic_capture_max_frames": 50,
        }
    },
}


@dataclass
class EventSystemConfig:
    enabled: bool = True
    profile: str = "default"
    async_observer_interval_ms: int = 250
    events: dict = field(default_factory=dict)
    hooks: dict = field(default_factory=dict)
    raw: dict = field(default_factory=dict)

    @classmethod
    def default(cls) -> "EventSystemConfig":
        data = copy.deepcopy(DEFAULT_EVENT_CONFIG)
        return cls.from_dict(data)

    @classmethod
    def from_dict(cls, data: dict) -> "EventSystemConfig":
        raw_data = data or {}
        merged = _deep_merge(copy.deepcopy(DEFAULT_EVENT_CONFIG), data or {})
        _apply_legacy_portal_detector_mode(raw_data, merged)
        _apply_legacy_loot_detector_weights(raw_data, merged)
        _apply_legacy_loot_performance_defaults(raw_data, merged)
        return cls(
            enabled=bool(merged.get("enabled", True)),
            profile=str(merged.get("profile", "default")),
            async_observer_interval_ms=max(0, int(merged.get("async_observer_interval_ms", 250) or 0)),
            events=merged.get("events", {}),
            hooks=merged.get("hooks", {}),
            raw=merged,
        )

    def event(self, event_type: str) -> dict:
        return self.events.get(event_type, {})

    def to_dict(self) -> dict:
        data = copy.deepcopy(self.raw)
        data["enabled"] = self.enabled
        data["profile"] = self.profile
        data["async_observer_interval_ms"] = int(self.async_observer_interval_ms)
        data["events"] = copy.deepcopy(self.events)
        data["hooks"] = copy.deepcopy(self.hooks)
        return data


def _deep_merge(base: dict, override: dict) -> dict:
    for key, value in (override or {}).items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            base[key] = _deep_merge(base[key], value)
        else:
            base[key] = value
    return base


def _apply_legacy_portal_detector_mode(raw_data: dict, merged: dict) -> None:
    raw_portal = ((raw_data.get("events") or {}).get("portal") or {}) if isinstance(raw_data, dict) else {}
    if not isinstance(raw_portal, dict):
        return
    if "detector_mode" in raw_portal or "feature_detector_enabled" not in raw_portal:
        return
    portal = (merged.get("events") or {}).get("portal")
    if not isinstance(portal, dict):
        return
    portal["detector_mode"] = "feature_then_template" if bool(raw_portal.get("feature_detector_enabled")) else "template"


def _apply_legacy_loot_detector_weights(raw_data: dict, merged: dict) -> None:
    raw_loot = ((raw_data.get("events") or {}).get("loot") or {}) if isinstance(raw_data, dict) else {}
    if not isinstance(raw_loot, dict) or "player_marker_exclusion_enabled" in raw_loot:
        return
    if not _is_legacy_loot_weight_triplet(raw_loot):
        return
    loot = (merged.get("events") or {}).get("loot")
    if not isinstance(loot, dict):
        return
    loot["template_weight"] = 0.46
    loot["shape_weight"] = 0.42
    loot["color_weight"] = 0.12


def _apply_legacy_loot_performance_defaults(raw_data: dict, merged: dict) -> None:
    raw_loot = ((raw_data.get("events") or {}).get("loot") or {}) if isinstance(raw_data, dict) else {}
    if not isinstance(raw_loot, dict):
        return
    if "roi_prefilter_enabled" in raw_loot:
        return
    loot = (merged.get("events") or {}).get("loot")
    if not isinstance(loot, dict):
        return
    loot["detection_interval_ms"] = 450
    loot["reuse_previous_detections"] = True
    loot["presence_confirm_frames"] = 2
    loot["masked_color_match_enabled"] = True
    loot["roi_prefilter_enabled"] = True
    loot["roi_min_area"] = 12
    loot["roi_max_size"] = 150
    loot["roi_expand"] = 48
    loot["player_center_mask_enabled"] = True
    loot["player_center_mask_overlay_enabled"] = True
    loot["player_center_mask_radius"] = 28


def _is_legacy_loot_weight_triplet(raw_loot: dict) -> bool:
    return bool(
        abs(float(raw_loot.get("template_weight", 0.46)) - 0.40) < 0.0001
        and abs(float(raw_loot.get("shape_weight", 0.42)) - 0.34) < 0.0001
        and abs(float(raw_loot.get("color_weight", 0.12)) - 0.26) < 0.0001
    )
