from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from gui.navigation_params import NavConfig

FieldKind = Literal["value", "text"]
WidgetWriter = Literal["value", "checked", "text"]
ConfigFieldPath = tuple[str | None, str]


@dataclass(frozen=True)
class FieldSpec:
    widget_attr: str
    sub_config_name: str | None
    attr_name: str
    kind: FieldKind
    writer: WidgetWriter
    group: str

    @property
    def field_path(self) -> ConfigFieldPath:
        return (self.sub_config_name, self.attr_name)


TEXT_FIELD_SPECS: tuple[FieldSpec, ...] = (
    FieldSpec("nav_wall_hsv_min_edit", "recognizer_params", "wall_hsv_min", "text", "text", "recognizer_hsv"),
    FieldSpec("nav_wall_hsv_max_edit", "recognizer_params", "wall_hsv_max", "text", "text", "recognizer_hsv"),
    FieldSpec("nav_fog_hsv_min_edit", "recognizer_params", "fog_hsv_min", "text", "text", "recognizer_hsv"),
    FieldSpec("nav_fog_hsv_max_edit", "recognizer_params", "fog_hsv_max", "text", "text", "recognizer_hsv"),
    FieldSpec(
        "nav_player_hsv_min_edit",
        "recognizer_params",
        "player_hsv_min",
        "text",
        "text",
        "recognizer_hsv",
    ),
    FieldSpec(
        "nav_player_hsv_max_edit",
        "recognizer_params",
        "player_hsv_max",
        "text",
        "text",
        "recognizer_hsv",
    ),
)


VALUE_FIELD_SPECS: tuple[FieldSpec, ...] = (
    FieldSpec("nav_chk_enable_wall", "recognizer_params", "enable_wall", "value", "checked", "recognizer_flags"),
    FieldSpec("nav_chk_enable_fog", "recognizer_params", "enable_fog", "value", "checked", "recognizer_flags"),
    FieldSpec(
        "nav_chk_clahe_enabled",
        "recognizer_params",
        "clahe_enabled",
        "value",
        "checked",
        "recognizer_flags",
    ),
    FieldSpec(
        "nav_chk_deepen_enabled",
        "recognizer_params",
        "deepen_enabled",
        "value",
        "checked",
        "recognizer_flags",
    ),
    FieldSpec(
        "nav_chk_gamma_enabled",
        "recognizer_params",
        "gamma_enabled",
        "value",
        "checked",
        "recognizer_flags",
    ),
    FieldSpec(
        "nav_chk_tophat_enabled",
        "recognizer_params",
        "tophat_enabled",
        "value",
        "checked",
        "recognizer_flags",
    ),
    FieldSpec(
        "nav_chk_sat_filter_enabled",
        "recognizer_params",
        "sat_filter_enabled",
        "value",
        "checked",
        "recognizer_flags",
    ),
    FieldSpec(
        "nav_chk_transparent_mode",
        "recognizer_params",
        "transparent_mode",
        "value",
        "checked",
        "recognizer_flags",
    ),
    FieldSpec("nav_clahe_clip_spin", "recognizer_params", "clahe_clip", "value", "value", "recognizer_values"),
    FieldSpec(
        "nav_deepen_factor_spin",
        "recognizer_params",
        "deepen_factor",
        "value",
        "value",
        "recognizer_values",
    ),
    FieldSpec("nav_gamma_value_spin", "recognizer_params", "gamma_value", "value", "value", "recognizer_values"),
    FieldSpec(
        "nav_tophat_strength_spin",
        "recognizer_params",
        "tophat_strength",
        "value",
        "value",
        "recognizer_values",
    ),
    FieldSpec(
        "nav_tophat_kernel_size_spin",
        "recognizer_params",
        "tophat_kernel_size",
        "value",
        "value",
        "recognizer_values",
    ),
    FieldSpec(
        "nav_sat_filter_thresh_spin",
        "recognizer_params",
        "sat_filter_thresh",
        "value",
        "value",
        "recognizer_values",
    ),
    FieldSpec("nav_edge_low_spin", "recognizer_params", "edge_low", "value", "value", "recognizer_values"),
    FieldSpec("nav_edge_high_spin", "recognizer_params", "edge_high", "value", "value", "recognizer_values"),
    FieldSpec("nav_blue_boost_spin", "recognizer_params", "blue_boost", "value", "value", "recognizer_values"),
    FieldSpec(
        "nav_trans_sat_penalty_spin",
        "recognizer_params",
        "trans_sat_penalty",
        "value",
        "value",
        "recognizer_values",
    ),
    FieldSpec(
        "nav_trans_wall_thresh_spin",
        "recognizer_params",
        "trans_wall_thresh",
        "value",
        "value",
        "recognizer_values",
    ),
    FieldSpec(
        "nav_sat_filter_radius_spin",
        "recognizer_params",
        "sat_filter_radius",
        "value",
        "value",
        "recognizer_values",
    ),
    FieldSpec("nav_wall_weight_spin", "recognizer_params", "wall_weight", "value", "value", "recognizer_values"),
    FieldSpec("nav_edge_weight_spin", "recognizer_params", "edge_weight", "value", "value", "recognizer_values"),
    FieldSpec("nav_clahe_grid_spin", "recognizer_params", "clahe_grid", "value", "value", "recognizer_values"),
    FieldSpec(
        "nav_kernel_small_spin",
        "recognizer_params",
        "kernel_small_size",
        "value",
        "value",
        "recognizer_values",
    ),
    FieldSpec(
        "nav_kernel_medium_spin",
        "recognizer_params",
        "kernel_medium_size",
        "value",
        "value",
        "recognizer_values",
    ),
    FieldSpec("nav_movement_scale_factor_spin", None, "movement_scale_factor", "value", "value", "movement"),
    FieldSpec("nav_game_view_map_size_spin", None, "game_view_map_size", "value", "value", "movement"),
    FieldSpec(
        "nav_movement_min_click_radius_spin",
        None,
        "movement_min_click_radius",
        "value",
        "value",
        "movement",
    ),
    FieldSpec(
        "nav_movement_max_click_radius_spin",
        None,
        "movement_max_click_radius",
        "value",
        "value",
        "movement",
    ),
    FieldSpec(
        "nav_movement_precision_click_max_radius_spin",
        None,
        "movement_precision_click_max_radius",
        "value",
        "value",
        "movement",
    ),
    FieldSpec("nav_auto_click_cooldown_spin", None, "auto_click_cooldown_ms", "value", "value", "movement"),
    FieldSpec("nav_auto_min_target_delta_spin", None, "auto_min_click_target_delta", "value", "value", "movement"),
    FieldSpec("nav_required_arrival_radius_spin", None, "required_arrival_radius", "value", "value", "path"),
    FieldSpec("nav_anchor_arrival_radius_spin", None, "anchor_arrival_radius", "value", "value", "path"),
    FieldSpec("nav_route_anchor_target_margin_spin", None, "route_anchor_target_margin", "value", "value", "path"),
    FieldSpec("nav_exact_goal_click_enabled_chk", None, "exact_goal_click_enabled", "value", "checked", "path"),
    FieldSpec("nav_exact_goal_click_radius_spin", None, "exact_goal_click_radius", "value", "value", "path"),
    FieldSpec("nav_exact_goal_click_cooldown_spin", None, "exact_goal_click_cooldown_ms", "value", "value", "path"),
    FieldSpec(
        "nav_exact_goal_recovery_suppress_spin",
        None,
        "exact_goal_recovery_suppress_ms",
        "value",
        "value",
        "path",
    ),
    FieldSpec("nav_movement_replan_throttle_spin", None, "movement_replan_throttle_ms", "value", "value", "path"),
    FieldSpec("nav_fallback_replan_interval_spin", None, "fallback_replan_interval_ms", "value", "value", "path"),
    FieldSpec(
        "nav_movement_progress_timeout_spin",
        None,
        "movement_progress_timeout_ms",
        "value",
        "value",
        "path",
    ),
    FieldSpec("nav_movement_min_progress_delta_spin", None, "movement_min_progress_delta", "value", "value", "path"),
    FieldSpec(
        "nav_movement_max_recover_attempts_spin",
        None,
        "movement_max_recover_attempts",
        "value",
        "value",
        "path",
    ),
    FieldSpec(
        "nav_movement_path_deviation_threshold_spin",
        None,
        "movement_path_deviation_threshold",
        "value",
        "value",
        "path",
    ),
    FieldSpec("nav_local_probe_forward_spin", None, "local_probe_forward_distance", "value", "value", "path"),
    FieldSpec("nav_local_probe_lateral_spin", None, "local_probe_lateral_distance", "value", "value", "path"),
    FieldSpec("nav_recovery_probe_forward_min_spin", None, "recovery_probe_forward_min", "value", "value", "path"),
    FieldSpec("nav_recovery_probe_forward_max_spin", None, "recovery_probe_forward_max", "value", "value", "path"),
    FieldSpec(
        "nav_recovery_probe_forward_multiplier_spin",
        None,
        "recovery_probe_forward_multiplier",
        "value",
        "value",
        "path",
    ),
    FieldSpec("nav_recovery_probe_lateral_spin", None, "recovery_probe_lateral_distance", "value", "value", "path"),
    FieldSpec("nav_event_approach_enabled_chk", None, "event_approach_enabled", "value", "checked", "events"),
    FieldSpec("nav_event_visible_margin_spin", None, "event_visible_margin", "value", "value", "events"),
    FieldSpec("nav_event_approach_lookahead_spin", None, "event_approach_lookahead", "value", "value", "events"),
    FieldSpec(
        "nav_event_approach_click_cooldown_spin",
        None,
        "event_approach_click_cooldown_ms",
        "value",
        "value",
        "events",
    ),
    FieldSpec("nav_event_stop_radius_spin", None, "event_stop_radius", "value", "value", "events"),
    FieldSpec("nav_event_settle_ms_spin", None, "event_settle_ms", "value", "value", "events"),
    FieldSpec("nav_event_stable_frames_spin", None, "event_stable_frames", "value", "value", "events"),
    FieldSpec(
        "nav_event_max_motion_per_frame_spin",
        None,
        "event_max_motion_per_frame",
        "value",
        "value",
        "events",
    ),
    FieldSpec("nav_event_route_backtrack_margin_spin", None, "event_route_backtrack_margin", "value", "value", "events"),
    FieldSpec(
        "nav_event_required_forward_margin_spin",
        None,
        "event_required_forward_margin",
        "value",
        "value",
        "events",
    ),
    FieldSpec("nav_event_exit_forward_margin_spin", None, "event_exit_forward_margin", "value", "value", "events"),
    FieldSpec("nav_event_fallback_player_radius_spin", None, "event_fallback_player_radius", "value", "value", "events"),
    FieldSpec("nav_event_fallback_static_margin_spin", None, "event_fallback_static_margin", "value", "value", "events"),
    FieldSpec("nav_bottom_click_guard_spin", None, "bottom_click_guard_pixels", "value", "value", "movement"),
    FieldSpec("nav_wall_erode_iterations_spin", None, "nav_wall_erode_iterations", "value", "value", "path"),
    FieldSpec("nav_path_start_clear_radius_spin", None, "path_start_clear_radius", "value", "value", "path"),
    FieldSpec("nav_path_walkable_snap_radius_spin", None, "path_walkable_snap_radius", "value", "value", "path"),
    FieldSpec(
        "nav_visual_check_interval_spin",
        None,
        "coordinate_visual_check_interval_ms",
        "value",
        "value",
        "visual_check",
    ),
    FieldSpec(
        "nav_visual_check_margin_spin",
        None,
        "coordinate_visual_check_margin",
        "value",
        "value",
        "visual_check",
    ),
    FieldSpec(
        "nav_visual_match_min_conf_spin",
        None,
        "coordinate_visual_match_min_confidence",
        "value",
        "value",
        "visual_check",
    ),
    FieldSpec(
        "nav_visual_mismatch_threshold_spin",
        None,
        "coordinate_visual_mismatch_threshold",
        "value",
        "value",
        "visual_check",
    ),
    FieldSpec(
        "nav_visual_mismatch_frames_spin",
        None,
        "coordinate_visual_mismatch_frames",
        "value",
        "value",
        "visual_check",
    ),
    FieldSpec(
        "nav_coord_raw_control_gap_spin",
        None,
        "coordinate_raw_control_gap_threshold",
        "value",
        "value",
        "coordinate_diagnostics",
    ),
    FieldSpec(
        "nav_coord_raw_jump_spin",
        None,
        "coordinate_raw_jump_threshold",
        "value",
        "value",
        "coordinate_diagnostics",
    ),
    FieldSpec(
        "nav_coord_route_deviation_spin",
        None,
        "coordinate_route_deviation_threshold",
        "value",
        "value",
        "coordinate_diagnostics",
    ),
    FieldSpec(
        "nav_coord_target_near_margin_spin",
        None,
        "coordinate_target_near_margin",
        "value",
        "value",
        "coordinate_diagnostics",
    ),
    FieldSpec(
        "nav_coord_target_stall_ms_spin",
        None,
        "coordinate_target_stall_ms",
        "value",
        "value",
        "coordinate_diagnostics",
    ),
    FieldSpec(
        "nav_coord_diagnostics_throttle_ms_spin",
        None,
        "coordinate_diagnostics_throttle_ms",
        "value",
        "value",
        "coordinate_diagnostics",
    ),
    FieldSpec(
        "nav_coord_recovery_enabled_chk",
        None,
        "coordinate_recovery_enabled",
        "value",
        "checked",
        "coordinate_diagnostics",
    ),
    FieldSpec(
        "nav_coord_recovery_score_spin",
        None,
        "coordinate_recovery_score_threshold",
        "value",
        "value",
        "coordinate_diagnostics",
    ),
    FieldSpec(
        "nav_coord_recovery_window_ms_spin",
        None,
        "coordinate_recovery_window_ms",
        "value",
        "value",
        "coordinate_diagnostics",
    ),
    FieldSpec(
        "nav_coord_recovery_cooldown_ms_spin",
        None,
        "coordinate_recovery_cooldown_ms",
        "value",
        "value",
        "coordinate_diagnostics",
    ),
    FieldSpec(
        "nav_coord_recovery_timeout_ms_spin",
        None,
        "coordinate_recovery_timeout_ms",
        "value",
        "value",
        "coordinate_diagnostics",
    ),
    FieldSpec(
        "nav_coord_long_f2f_tracking_ms_spin",
        None,
        "coordinate_long_f2f_tracking_ms",
        "value",
        "value",
        "coordinate_diagnostics",
    ),
    FieldSpec(
        "nav_coord_localization_sample_interval_ms_spin",
        None,
        "coordinate_localization_sample_interval_ms",
        "value",
        "value",
        "coordinate_diagnostics",
    ),
    FieldSpec("nav_fps_spin", None, "fps", "value", "value", "runtime"),
)


BOUND_FIELD_SPECS: tuple[FieldSpec, ...] = TEXT_FIELD_SPECS + VALUE_FIELD_SPECS


def resolve_widget(panel, spec: FieldSpec):
    return getattr(panel, spec.widget_attr)


def config_value(config: NavConfig, spec: FieldSpec):
    target = config
    if spec.sub_config_name:
        target = getattr(config, spec.sub_config_name)
    return getattr(target, spec.attr_name)
