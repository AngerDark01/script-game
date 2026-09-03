from __future__ import annotations

from dataclasses import dataclass


@dataclass
class LootEventConfig:
    enabled: bool = True
    priority: int = 60
    navigation_approach_enabled: bool = True
    detector_mode: str = "async_feature_match"
    weighted_threshold: float = 0.54
    collect_threshold: float = 0.28
    max_blobs_per_frame: int = 3
    top_k_per_template: int = 24
    detection_interval_ms: int = 450
    reuse_previous_detections: bool = True
    presence_confirm_frames: int = 2
    masked_color_match_enabled: bool = True
    roi_prefilter_enabled: bool = True
    roi_min_area: int = 12
    roi_max_size: int = 150
    roi_expand: int = 48
    min_color_score: float = 0.12
    min_template_score: float = 0.25
    min_shape_score: float = 0.22
    template_weight: float = 0.46
    shape_weight: float = 0.42
    color_weight: float = 0.12
    player_marker_exclusion_enabled: bool = True
    player_marker_template_threshold: float = 0.75
    player_marker_exact_template_threshold: float = 0.96
    player_marker_blue_ratio_threshold: float = 0.30
    player_marker_triangle_score_threshold: float = 0.54
    player_center_mask_enabled: bool = True
    player_center_mask_overlay_enabled: bool = True
    player_center_mask_radius: int = 28
    scales: str = "0.75,0.85,1.0,1.15,1.3"
    feature_match_threshold: float = 0.64
    feature_match_collect_threshold: float = 0.38
    feature_match_top_k_per_template: int = 2
    feature_match_max_candidates: int = 5
    feature_match_search_padding: int = 48
    feature_match_scales: str = "0.75,0.85,1.0"
    async_full_scan_interval_ms: int = 1000
    async_track_refresh_ms: int = 8000
    async_track_ttl_ms: int = 8000
    async_known_seed_radius: int = 72
    stable_frames: int = 2
    localization_cluster_radius: int = 72
    stable_variance: float = 2200.0
    dedupe_radius: int = 110
    localization_max_samples: int = 8
    localization_cluster_ttl_ms: int = 8000
    localization_emit_interval_ms: int = 150
    memory_confirm_frames: int = 1
    target_update_mode: str = "lock_after_confirm"
    target_update_max_drift: int = 0
    arrival_radius: int = 90
    pickup_radius: int = 58
    pickup_key: str = "a"
    post_pickup_wait_ms: int = 450
    absence_confirm_frames: int = 2
    absence_frame_ms: int = 250
    pickup_press_limit: int = 3
    retry_limit: int = 1
    cooldown_ms: int = 45000
    cooldown_radius: int = 180
    type_cooldown_ms: int = 0
    diagnostic_capture_enabled: bool = False
    diagnostic_stage_dump_enabled: bool = False
    diagnostic_capture_interval_ms: int = 1000
    diagnostic_capture_max_frames: int = 50

    @classmethod
    def from_dict(cls, data: dict | None) -> "LootEventConfig":
        values = data or {}
        template_weight = float(values.get("template_weight", 0.46))
        shape_weight = float(values.get("shape_weight", 0.42))
        color_weight = float(values.get("color_weight", 0.12))
        if "player_marker_exclusion_enabled" not in values and _uses_legacy_default_weights(template_weight, shape_weight, color_weight):
            template_weight = 0.46
            shape_weight = 0.42
            color_weight = 0.12
        masked_color_match_enabled = bool(values.get("masked_color_match_enabled", True))
        if "roi_prefilter_enabled" not in values and values.get("masked_color_match_enabled") is False:
            masked_color_match_enabled = True
        return cls(
            enabled=bool(values.get("enabled", True)),
            priority=int(values.get("priority", 60)),
            navigation_approach_enabled=bool(values.get("navigation_approach_enabled", True)),
            detector_mode=str(values.get("detector_mode", "async_feature_match")),
            weighted_threshold=float(values.get("weighted_threshold", 0.54)),
            collect_threshold=float(values.get("collect_threshold", 0.28)),
            max_blobs_per_frame=int(values.get("max_blobs_per_frame", 3)),
            top_k_per_template=int(values.get("top_k_per_template", 24)),
            detection_interval_ms=int(values.get("detection_interval_ms", 450)),
            reuse_previous_detections=bool(values.get("reuse_previous_detections", True)),
            presence_confirm_frames=int(values.get("presence_confirm_frames", 2)),
            masked_color_match_enabled=masked_color_match_enabled,
            roi_prefilter_enabled=bool(values.get("roi_prefilter_enabled", True)),
            roi_min_area=int(values.get("roi_min_area", 12)),
            roi_max_size=int(values.get("roi_max_size", 150)),
            roi_expand=int(values.get("roi_expand", 48)),
            min_color_score=float(values.get("min_color_score", 0.12)),
            min_template_score=float(values.get("min_template_score", 0.25)),
            min_shape_score=float(values.get("min_shape_score", 0.22)),
            template_weight=template_weight,
            shape_weight=shape_weight,
            color_weight=color_weight,
            player_marker_exclusion_enabled=bool(values.get("player_marker_exclusion_enabled", True)),
            player_marker_template_threshold=float(values.get("player_marker_template_threshold", 0.75)),
            player_marker_exact_template_threshold=float(values.get("player_marker_exact_template_threshold", 0.96)),
            player_marker_blue_ratio_threshold=float(values.get("player_marker_blue_ratio_threshold", 0.30)),
            player_marker_triangle_score_threshold=float(values.get("player_marker_triangle_score_threshold", 0.54)),
            player_center_mask_enabled=bool(values.get("player_center_mask_enabled", True)),
            player_center_mask_overlay_enabled=bool(values.get("player_center_mask_overlay_enabled", True)),
            player_center_mask_radius=int(values.get("player_center_mask_radius", 28)),
            scales=str(values.get("scales", "0.75,0.85,1.0,1.15,1.3")),
            feature_match_threshold=float(values.get("feature_match_threshold", 0.64)),
            feature_match_collect_threshold=float(values.get("feature_match_collect_threshold", 0.38)),
            feature_match_top_k_per_template=int(values.get("feature_match_top_k_per_template", 2)),
            feature_match_max_candidates=int(values.get("feature_match_max_candidates", 5)),
            feature_match_search_padding=int(values.get("feature_match_search_padding", 48)),
            feature_match_scales=str(values.get("feature_match_scales", "0.75,0.85,1.0")),
            async_full_scan_interval_ms=int(values.get("async_full_scan_interval_ms", 1000)),
            async_track_refresh_ms=int(values.get("async_track_refresh_ms", 8000)),
            async_track_ttl_ms=int(values.get("async_track_ttl_ms", 8000)),
            async_known_seed_radius=int(values.get("async_known_seed_radius", 72)),
            stable_frames=int(values.get("stable_frames", 2)),
            localization_cluster_radius=int(values.get("localization_cluster_radius", 72)),
            stable_variance=float(values.get("stable_variance", 2200.0)),
            dedupe_radius=int(values.get("dedupe_radius", 110)),
            localization_max_samples=int(values.get("localization_max_samples", 8)),
            localization_cluster_ttl_ms=int(values.get("localization_cluster_ttl_ms", 8000)),
            localization_emit_interval_ms=int(values.get("localization_emit_interval_ms", 150)),
            memory_confirm_frames=int(values.get("memory_confirm_frames", 1)),
            target_update_mode=str(values.get("target_update_mode", "lock_after_confirm") or "lock_after_confirm"),
            target_update_max_drift=int(values.get("target_update_max_drift", 0)),
            arrival_radius=int(values.get("arrival_radius", 90)),
            pickup_radius=int(values.get("pickup_radius", 58)),
            pickup_key=str(values.get("pickup_key", "a") or "a").strip() or "a",
            post_pickup_wait_ms=int(values.get("post_pickup_wait_ms", 450)),
            absence_confirm_frames=int(values.get("absence_confirm_frames", 2)),
            absence_frame_ms=int(values.get("absence_frame_ms", 250)),
            pickup_press_limit=int(values.get("pickup_press_limit", 3)),
            retry_limit=int(values.get("retry_limit", 1)),
            cooldown_ms=int(values.get("cooldown_ms", 45000)),
            cooldown_radius=int(values.get("cooldown_radius", 180)),
            type_cooldown_ms=int(values.get("type_cooldown_ms", 0)),
            diagnostic_capture_enabled=bool(values.get("diagnostic_capture_enabled", False)),
            diagnostic_stage_dump_enabled=bool(values.get("diagnostic_stage_dump_enabled", False)),
            diagnostic_capture_interval_ms=int(values.get("diagnostic_capture_interval_ms", 1000)),
            diagnostic_capture_max_frames=int(values.get("diagnostic_capture_max_frames", 50)),
        )

    def to_dict(self) -> dict:
        return dict(self.__dict__)

    def scale_values(self) -> list[float]:
        return _parse_scale_values(self.scales, [0.75, 0.85, 1.0, 1.15, 1.3])

    def feature_match_scale_values(self) -> list[float]:
        return _parse_scale_values(self.feature_match_scales, [0.75, 0.85, 1.0])


def _parse_scale_values(raw: str, fallback: list[float]) -> list[float]:
        values: list[float] = []
        for item in str(raw or "").split(","):
            item = item.strip()
            if not item:
                continue
            try:
                value = float(item)
            except ValueError:
                continue
            if value > 0:
                values.append(value)
        return values or list(fallback)


def _uses_legacy_default_weights(template_weight: float, shape_weight: float, color_weight: float) -> bool:
    return bool(
        abs(float(template_weight) - 0.40) < 0.0001
        and abs(float(shape_weight) - 0.34) < 0.0001
        and abs(float(color_weight) - 0.26) < 0.0001
    )
