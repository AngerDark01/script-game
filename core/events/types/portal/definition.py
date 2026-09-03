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
            "navigation_approach_enabled": {
                "type": "bool",
                "label": "启用导航停靠",
                "default": True,
                "help": "开启后，导航层会在事件进入真实视野后先靠近并停稳，再交给传送门事件处理器按键/点击。",
            },
            "interaction": {"type": "choice", "label": "interaction", "choices": ["click", "key"]},
            "detector_mode": {
                "type": "choice",
                "label": "小地图识别模式",
                "choices": ["feature_then_template", "feature", "shape_color", "template"],
                "default": "shape_color",
                "help": "shape_color 会同时检查蓝色核心、白灰外环、轮廓和颜色，通常比纯 feature/template 更不容易误识别。",
            },
            "minimap_threshold": {
                "type": "float",
                "label": "小地图识别阈值",
                "min": 0.1,
                "max": 1.0,
                "step": 0.01,
                "default": 0.74,
                "help": "提高会减少误识别，但可能漏掉弱传送门；降低会增加召回，也更容易重复或误检。",
            },
            "max_candidates": {"type": "int", "label": "每帧最大候选数", "min": 1, "max": 12, "default": 2},
            "minimap_nms_radius": {
                "type": "int",
                "label": "小地图命中合并半径",
                "min": 0,
                "max": 100,
                "default": 28,
                "help": "单位是小地图像素。用于在进入定位前合并同一图标的近距离重复命中；0 表示关闭。",
            },
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
            "stable_frames": {"type": "int", "label": "稳定帧数", "min": 1, "max": 10, "default": 3},
            "localization_cluster_radius": {
                "type": "int",
                "label": "定位聚类半径",
                "min": 20,
                "max": 300,
                "default": 96,
                "help": "同一个传送门在多帧投影后如果落在这个半径内，会进入同一个稳定簇。",
            },
            "stable_variance": {"type": "float", "label": "稳定方差上限", "min": 100.0, "max": 10000.0, "default": 1600.0},
            "dedupe_radius": {
                "type": "int",
                "label": "任务去重半径",
                "min": 20,
                "max": 300,
                "default": 96,
                "help": "稳定定位后写入事件记忆时使用。同一传送门重复生成任务时应调大；真实相邻双门被合并时再调小。",
            },
            "localization_max_samples": {"type": "int", "label": "定位最大样本数", "min": 3, "max": 30, "default": 12},
            "localization_cluster_ttl_ms": {
                "type": "int",
                "label": "定位簇保留时间 ms",
                "min": 1000,
                "max": 60000,
                "step": 500,
                "default": 12000,
            },
            "localization_emit_interval_ms": {
                "type": "int",
                "label": "稳定结果输出间隔 ms",
                "min": 50,
                "max": 2000,
                "step": 50,
                "default": 700,
            },
            "memory_confirm_frames": {"type": "int", "label": "任务确认帧数", "min": 1, "max": 10, "default": 1},
            "target_update_mode": {
                "type": "choice",
                "label": "目标锁点模式",
                "choices": ["lock_after_confirm", "limited_after_confirm", "continuous"],
                "default": "limited_after_confirm",
                "help": "传送门任务确认后如何更新导航目标。limited_after_confirm 会锁住目标，只允许 target_update_max_drift 范围内的小修正。",
            },
            "target_update_max_drift": {
                "type": "int",
                "label": "锁点允许漂移",
                "min": 0,
                "max": 120,
                "default": 18,
                "help": "单位是地图像素。目标锁定后，超过该距离的新观测只刷新可见性，不拖动导航目标。",
            },
            "arrival_radius": {"type": "int", "label": "arrival_radius (approach)", "min": 10, "max": 300, "step": 2, "default": 80},
            "interact_radius": {"type": "int", "label": "interact_radius (press D distance)", "min": 1, "max": 120, "step": 1, "default": 36},
            "portal_point_click_wait_ms": {"type": "int", "label": "portal point click wait ms", "min": 0, "max": 2000, "step": 50, "default": 350},
            "cooldown_ms": {"type": "int", "label": "cooldown_ms (position)", "min": 0, "max": 600000, "step": 1000, "default": 120000},
            "cooldown_radius": {"type": "int", "label": "完成冷却半径", "min": 20, "max": 500, "default": 260},
            "exit_complete_radius": {"type": "int", "label": "出口完成合并半径", "min": 20, "max": 500, "default": 120},
            "type_cooldown_ms": {"type": "int", "label": "type_cooldown_ms (after teleport)", "min": 0, "max": 60000, "step": 500, "default": 10000},
            "retry_limit": {"type": "int", "label": "retry limit", "min": 0, "max": 5},
        }

    def create_detector(self, config):
        return PortalMinimapDetector(PortalEventConfig.from_dict(config))

    def create_handler(self, config):
        return PortalEventHandler(PortalEventConfig.from_dict(config))
