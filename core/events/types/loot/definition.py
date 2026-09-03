from __future__ import annotations

from core.events.base.definition import EventDefinition

from .config import LootEventConfig
from .handler import LootPickupHandler
from .minimap_detector import LootMinimapDetector


class LootEventDefinition(EventDefinition):
    event_type = "loot"
    display_name = "Loot"
    description = "Detect loot blobs on the minimap, navigate near the blob, press A inside pickup radius, and finish after the blob disappears."

    def default_config(self) -> dict:
        return LootEventConfig().to_dict()

    def config_schema(self) -> dict:
        return {
            "enabled": {"type": "bool", "label": "enabled"},
            "priority": {"type": "int", "label": "priority", "min": 0, "max": 1000, "default": 60},
            "navigation_approach_enabled": {
                "type": "bool",
                "label": "启用导航停靠",
                "default": True,
                "help": "开启后，导航层会在事件进入真实视野后先靠近并停稳，再交给掉落物事件处理器拾取。",
            },
            "detector_mode": {
                "type": "choice",
                "label": "minimap detector mode",
                "choices": ["async_feature_match", "feature_match", "weighted_blob"],
                "default": "async_feature_match",
            },
            "weighted_threshold": {"type": "float", "label": "weighted threshold", "min": 0.1, "max": 1.0, "step": 0.01, "default": 0.54},
            "collect_threshold": {"type": "float", "label": "candidate collect threshold", "min": 0.05, "max": 1.0, "step": 0.01, "default": 0.28},
            "max_blobs_per_frame": {"type": "int", "label": "max loot blobs per frame", "min": 1, "max": 8, "default": 3},
            "top_k_per_template": {"type": "int", "label": "top hits per template", "min": 1, "max": 80, "default": 24},
            "detection_interval_ms": {"type": "int", "label": "detection interval ms", "min": 0, "max": 3000, "step": 50, "default": 450},
            "reuse_previous_detections": {"type": "bool", "label": "reuse previous detections", "default": True},
            "presence_confirm_frames": {"type": "int", "label": "presence confirm frames", "min": 1, "max": 6, "default": 2},
            "masked_color_match_enabled": {"type": "bool", "label": "masked color match", "default": True},
            "roi_prefilter_enabled": {"type": "bool", "label": "roi prefilter", "default": True},
            "roi_min_area": {"type": "int", "label": "roi min area", "min": 1, "max": 500, "default": 12},
            "roi_max_size": {"type": "int", "label": "roi max size", "min": 20, "max": 500, "default": 150},
            "roi_expand": {"type": "int", "label": "roi expand", "min": 0, "max": 160, "default": 48},
            "min_color_score": {"type": "float", "label": "min color score", "min": 0.0, "max": 1.0, "step": 0.01, "default": 0.12},
            "min_template_score": {"type": "float", "label": "min template score", "min": 0.0, "max": 1.0, "step": 0.01, "default": 0.25},
            "min_shape_score": {"type": "float", "label": "min shape score", "min": 0.0, "max": 1.0, "step": 0.01, "default": 0.22},
            "template_weight": {"type": "float", "label": "template weight", "min": 0.0, "max": 1.0, "step": 0.01, "default": 0.46},
            "shape_weight": {"type": "float", "label": "shape weight", "min": 0.0, "max": 1.0, "step": 0.01, "default": 0.42},
            "color_weight": {"type": "float", "label": "color weight", "min": 0.0, "max": 1.0, "step": 0.01, "default": 0.12},
            "player_marker_exclusion_enabled": {"type": "bool", "label": "exclude player marker", "default": True},
            "player_marker_template_threshold": {"type": "float", "label": "player marker template threshold", "min": 0.1, "max": 1.0, "step": 0.01, "default": 0.75},
            "player_marker_exact_template_threshold": {"type": "float", "label": "player marker exact threshold", "min": 0.1, "max": 1.0, "step": 0.01, "default": 0.96},
            "player_marker_blue_ratio_threshold": {"type": "float", "label": "player marker blue ratio threshold", "min": 0.0, "max": 1.0, "step": 0.01, "default": 0.30},
            "player_marker_triangle_score_threshold": {"type": "float", "label": "player marker triangle threshold", "min": 0.0, "max": 1.0, "step": 0.01, "default": 0.54},
            "player_center_mask_enabled": {
                "type": "bool",
                "label": "启用中心人物遮罩",
                "default": True,
                "help": "只在小地图中心区域被确认像人物箭头时生效，用于先擦除固定玩家图标，减少掉落物误检。",
            },
            "player_center_mask_overlay_enabled": {
                "type": "bool",
                "label": "显示人物遮罩范围",
                "default": True,
                "help": "在导航地图上用半透明圆圈显示中心人物擦除半径，方便调参；只影响显示，不影响识别。",
            },
            "player_center_mask_radius": {
                "type": "int",
                "label": "中心人物擦除半径",
                "min": 4,
                "max": 80,
                "default": 28,
                "help": "单位是小地图像素。数值越大，中心人物图标擦得越干净，但可能吞掉贴近人物的掉落物。",
            },
            "scales": {"type": "str", "label": "template scales", "default": "0.75,0.85,1.0,1.15,1.3"},
            "feature_match_threshold": {"type": "float", "label": "feature match threshold", "min": 0.1, "max": 1.0, "step": 0.01, "default": 0.64},
            "feature_match_collect_threshold": {"type": "float", "label": "feature collect threshold", "min": 0.05, "max": 1.0, "step": 0.01, "default": 0.38},
            "feature_match_top_k_per_template": {"type": "int", "label": "feature top hits per template", "min": 1, "max": 20, "default": 2},
            "feature_match_max_candidates": {"type": "int", "label": "feature max candidates", "min": 1, "max": 20, "default": 5},
            "feature_match_search_padding": {"type": "int", "label": "feature search padding", "min": 8, "max": 160, "default": 48},
            "feature_match_scales": {"type": "str", "label": "feature template scales", "default": "0.75,0.85,1.0"},
            "async_full_scan_interval_ms": {"type": "int", "label": "async full scan interval ms", "min": 200, "max": 10000, "step": 100, "default": 1000},
            "async_track_refresh_ms": {"type": "int", "label": "async track refresh ms", "min": 1000, "max": 60000, "step": 500, "default": 8000},
            "async_track_ttl_ms": {"type": "int", "label": "async track ttl ms", "min": 1000, "max": 60000, "step": 500, "default": 8000},
            "async_known_seed_radius": {"type": "int", "label": "async known seed radius", "min": 10, "max": 300, "default": 72},
            "stable_frames": {"type": "int", "label": "stable frames", "min": 1, "max": 8, "default": 2},
            "localization_cluster_radius": {"type": "int", "label": "localization cluster radius", "min": 20, "max": 300, "default": 72},
            "stable_variance": {"type": "float", "label": "stable variance", "min": 100.0, "max": 20000.0, "step": 50.0, "default": 2200.0},
            "dedupe_radius": {"type": "int", "label": "memory dedupe radius", "min": 20, "max": 300, "default": 110},
            "localization_max_samples": {"type": "int", "label": "localization max samples", "min": 3, "max": 30, "default": 8},
            "localization_cluster_ttl_ms": {"type": "int", "label": "localization cluster ttl ms", "min": 1000, "max": 60000, "step": 500, "default": 8000},
            "localization_emit_interval_ms": {"type": "int", "label": "localization emit interval ms", "min": 50, "max": 1000, "step": 50, "default": 150},
            "memory_confirm_frames": {"type": "int", "label": "memory confirm frames", "min": 1, "max": 10, "default": 1},
            "target_update_mode": {
                "type": "choice",
                "label": "target update mode",
                "choices": ["lock_after_confirm", "limited_after_confirm", "continuous"],
                "default": "lock_after_confirm",
            },
            "target_update_max_drift": {"type": "int", "label": "target update max drift", "min": 0, "max": 120, "default": 0},
            "arrival_radius": {"type": "int", "label": "arrival radius", "min": 10, "max": 300, "step": 2, "default": 90},
            "pickup_radius": {"type": "int", "label": "pickup radius", "min": 5, "max": 200, "step": 1, "default": 58},
            "pickup_key": {
                "type": "choice",
                "label": "pickup key",
                "choices": ["a", "b", "c", "d", "e", "f", "space"],
                "default": "a",
            },
            "post_pickup_wait_ms": {"type": "int", "label": "post pickup wait ms", "min": 0, "max": 3000, "step": 50, "default": 450},
            "absence_confirm_frames": {"type": "int", "label": "absence confirm frames", "min": 1, "max": 10, "default": 2},
            "absence_frame_ms": {"type": "int", "label": "absence frame ms", "min": 50, "max": 2000, "step": 50, "default": 250},
            "pickup_press_limit": {"type": "int", "label": "pickup press limit", "min": 1, "max": 10, "default": 3},
            "retry_limit": {"type": "int", "label": "task retry limit", "min": 1, "max": 5, "default": 1},
            "cooldown_ms": {"type": "int", "label": "cooldown ms", "min": 0, "max": 600000, "step": 1000, "default": 45000},
            "cooldown_radius": {"type": "int", "label": "cooldown radius", "min": 20, "max": 500, "default": 180},
            "type_cooldown_ms": {"type": "int", "label": "type cooldown ms", "min": 0, "max": 600000, "step": 1000, "default": 0},
            "diagnostic_capture_enabled": {"type": "bool", "label": "diagnostic capture", "default": False},
            "diagnostic_stage_dump_enabled": {"type": "bool", "label": "diagnostic stage dump", "default": False},
            "diagnostic_capture_interval_ms": {"type": "int", "label": "diagnostic capture interval ms", "min": 200, "max": 10000, "step": 100, "default": 1000},
            "diagnostic_capture_max_frames": {"type": "int", "label": "diagnostic capture max frames", "min": 1, "max": 500, "default": 50},
        }

    def create_detector(self, config):
        return LootMinimapDetector(LootEventConfig.from_dict(config))

    def create_handler(self, config):
        return LootPickupHandler(LootEventConfig.from_dict(config))
