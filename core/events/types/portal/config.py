from __future__ import annotations

from dataclasses import dataclass


@dataclass
class PortalEventConfig:
    enabled: bool = True
    priority: int = 100
    navigation_approach_enabled: bool = True
    interaction: str = "key"
    detector_mode: str = "shape_color"
    minimap_threshold: float = 0.74
    max_candidates: int = 2
    minimap_nms_radius: int = 28
    min_blue_ratio: float = 0.08
    feature_detector_enabled: bool = True
    feature_hue_min: int = 82
    feature_hue_max: int = 136
    feature_sat_min: int = 55
    feature_val_min: int = 95
    feature_min_blue_pixels: int = 36
    feature_max_blue_pixels: int = 420
    shape_outer_sat_max: int = 115
    shape_outer_val_min: int = 105
    shape_min_blue_score: float = 0.28
    shape_min_outer_score: float = 0.18
    shape_min_shape_score: float = 0.30
    shape_min_outer_pixels: int = 14
    shape_signature_min_outer_score: float = 0.45
    shape_signature_min_edge_score: float = 0.40
    shape_signature_min_color_score: float = 0.82
    shape_signature_score_scale: float = 1.30
    stable_frames: int = 3
    localization_cluster_radius: int = 96
    stable_variance: float = 1600.0
    dedupe_radius: int = 96
    localization_max_samples: int = 12
    localization_cluster_ttl_ms: int = 12000
    localization_emit_interval_ms: int = 700
    memory_confirm_frames: int = 1
    target_update_mode: str = "limited_after_confirm"
    target_update_max_drift: int = 18
    arrival_radius: int = 80
    interact_radius: int = 36
    retry_limit: int = 2
    cooldown_ms: int = 120000
    cooldown_radius: int = 260
    exit_complete_radius: int = 120
    type_cooldown_ms: int = 10000
    click_wait_ms: int = 1200
    confirm_timeout_ms: int = 2500
    portal_point_click_wait_ms: int = 350
    post_interact_wait_ms: int = 800
    teleport_timeout_ms: int = 6000
    teleport_min_distance: int = 180
    environment_change_threshold: float = 0.18

    @classmethod
    def from_dict(cls, data: dict | None):
        values = data or {}
        detector_mode = str(values.get("detector_mode", "") or "").strip()
        if not detector_mode:
            if "feature_detector_enabled" in values:
                detector_mode = "feature_then_template" if bool(values.get("feature_detector_enabled")) else "template"
            else:
                detector_mode = "shape_color"
        return cls(
            enabled=bool(values.get("enabled", True)),
            priority=int(values.get("priority", 100)),
            navigation_approach_enabled=bool(values.get("navigation_approach_enabled", True)),
            interaction=str(values.get("interaction", "key")),
            detector_mode=detector_mode,
            minimap_threshold=float(values.get("minimap_threshold", 0.74)),
            max_candidates=int(values.get("max_candidates", 2)),
            minimap_nms_radius=int(values.get("minimap_nms_radius", 28)),
            min_blue_ratio=float(values.get("min_blue_ratio", 0.08)),
            feature_detector_enabled=bool(values.get("feature_detector_enabled", True)),
            feature_hue_min=int(values.get("feature_hue_min", 82)),
            feature_hue_max=int(values.get("feature_hue_max", 136)),
            feature_sat_min=int(values.get("feature_sat_min", 55)),
            feature_val_min=int(values.get("feature_val_min", 95)),
            feature_min_blue_pixels=int(values.get("feature_min_blue_pixels", 36)),
            feature_max_blue_pixels=int(values.get("feature_max_blue_pixels", 420)),
            shape_outer_sat_max=int(values.get("shape_outer_sat_max", 115)),
            shape_outer_val_min=int(values.get("shape_outer_val_min", 105)),
            shape_min_blue_score=float(values.get("shape_min_blue_score", 0.28)),
            shape_min_outer_score=float(values.get("shape_min_outer_score", 0.18)),
            shape_min_shape_score=float(values.get("shape_min_shape_score", 0.30)),
            shape_min_outer_pixels=int(values.get("shape_min_outer_pixels", 14)),
            shape_signature_min_outer_score=float(values.get("shape_signature_min_outer_score", 0.45)),
            shape_signature_min_edge_score=float(values.get("shape_signature_min_edge_score", 0.40)),
            shape_signature_min_color_score=float(values.get("shape_signature_min_color_score", 0.82)),
            shape_signature_score_scale=float(values.get("shape_signature_score_scale", 1.30)),
            stable_frames=int(values.get("stable_frames", values.get("confirm_frames", 3))),
            localization_cluster_radius=int(values.get("localization_cluster_radius", 96)),
            stable_variance=float(values.get("stable_variance", 1600.0)),
            dedupe_radius=int(values.get("dedupe_radius", 96)),
            localization_max_samples=int(values.get("localization_max_samples", 12)),
            localization_cluster_ttl_ms=int(values.get("localization_cluster_ttl_ms", 12000)),
            localization_emit_interval_ms=int(values.get("localization_emit_interval_ms", 700)),
            memory_confirm_frames=int(values.get("memory_confirm_frames", 1)),
            target_update_mode=str(values.get("target_update_mode", "limited_after_confirm") or "limited_after_confirm"),
            target_update_max_drift=int(values.get("target_update_max_drift", 18)),
            arrival_radius=int(values.get("arrival_radius", 80)),
            interact_radius=int(values.get("interact_radius", 36)),
            retry_limit=int(values.get("retry_limit", 2)),
            cooldown_ms=int(values.get("cooldown_ms", 120000)),
            cooldown_radius=int(values.get("cooldown_radius", 260)),
            exit_complete_radius=int(values.get("exit_complete_radius", 120)),
            type_cooldown_ms=int(values.get("type_cooldown_ms", 10000)),
            click_wait_ms=int(values.get("click_wait_ms", 1200)),
            confirm_timeout_ms=int(values.get("confirm_timeout_ms", 2500)),
            portal_point_click_wait_ms=int(values.get("portal_point_click_wait_ms", 350)),
            post_interact_wait_ms=int(values.get("post_interact_wait_ms", 800)),
            teleport_timeout_ms=int(values.get("teleport_timeout_ms", 6000)),
            teleport_min_distance=int(values.get("teleport_min_distance", 180)),
            environment_change_threshold=float(values.get("environment_change_threshold", 0.18)),
        )

    def to_dict(self) -> dict:
        return dict(self.__dict__)
