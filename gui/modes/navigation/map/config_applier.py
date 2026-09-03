from __future__ import annotations

from core.events.debug import event_log


def apply_navigation_config_to_core(
    nav_config,
    *,
    nav_core,
    path_finder,
    motion_controller,
    navigation_task_controller,
) -> bool:
    """Apply a NavConfig to navigation runtime objects while preserving map npz authority."""
    if not nav_core or not nav_config:
        return False

    nav_core.recognizer.set_params(nav_config.recognizer_params.__dict__)
    map_draw_scale = float(getattr(nav_core, "map_draw_scale", nav_core.draw_scale))
    if abs(float(nav_config.draw_scale) - map_draw_scale) > 0.001:
        event_log(
            "navigation draw_scale config mismatch",
            config_draw_scale=float(nav_config.draw_scale),
            map_draw_scale=map_draw_scale,
            action="use_map_npz_draw_scale",
        )
        nav_config.draw_scale = map_draw_scale
    nav_core.draw_scale = map_draw_scale
    nav_core.wall_match_close_kernel_size = max(
        1,
        int(
            getattr(
                nav_core,
                "map_wall_match_close_kernel_size",
                getattr(nav_config, "wall_match_close_kernel_size", 3),
            )
        ),
    )
    nav_core.rebuild_navigation_wall_layer(
        erode_iterations=nav_config.nav_wall_erode_iterations,
    )
    nav_core.last_player_local_pos = None

    path_finder.start_clear_radius = max(0, int(nav_config.path_start_clear_radius))
    path_finder.walkable_snap_radius = max(0, int(nav_config.path_walkable_snap_radius))
    event_log(
        "navigation obstacle config applied",
        nav_wall_erode_iterations=nav_config.nav_wall_erode_iterations,
        path_start_clear_radius=path_finder.start_clear_radius,
        path_walkable_snap_radius=path_finder.walkable_snap_radius,
        draw_scale=nav_core.draw_scale,
        wall_match_close_kernel_size=nav_core.wall_match_close_kernel_size,
    )

    nav_core.get_map_image()
    apply_motion_controller_config(nav_config, motion_controller)
    configure_navigation_task_controller(
        nav_config,
        nav_core=nav_core,
        navigation_task_controller=navigation_task_controller,
    )
    return True


def apply_motion_controller_config(nav_config, motion_controller) -> None:
    if not nav_config or not nav_config.game_screen_center:
        return
    motion_controller.set_params(
        game_screen_center=nav_config.game_screen_center,
        movement_scale_factor=nav_config.movement_scale_factor,
        movement_min_click_radius=nav_config.movement_min_click_radius,
        movement_max_click_radius=nav_config.movement_max_click_radius,
        movement_precision_click_max_radius=nav_config.movement_precision_click_max_radius,
        bottom_click_guard_pixels=nav_config.bottom_click_guard_pixels,
    )


def configure_navigation_task_controller(
    nav_config,
    *,
    nav_core,
    navigation_task_controller,
) -> None:
    if not nav_config:
        return

    if nav_core:
        nav_core.visual_check_interval_ms = max(0, int(nav_config.coordinate_visual_check_interval_ms))
        nav_core.visual_check_margin = max(0, int(nav_config.coordinate_visual_check_margin))
        nav_core.visual_check_min_confidence = max(
            0.0,
            min(0.99, float(nav_config.coordinate_visual_match_min_confidence)),
        )
        nav_core.visual_mismatch_threshold = max(0.0, float(nav_config.coordinate_visual_mismatch_threshold))

    diagnostics = navigation_task_controller.coordinate_diagnostics
    diagnostics.raw_control_gap_threshold = max(0.0, float(nav_config.coordinate_raw_control_gap_threshold))
    diagnostics.raw_jump_threshold = max(0.0, float(nav_config.coordinate_raw_jump_threshold))
    diagnostics.route_deviation_threshold = max(0.0, float(nav_config.coordinate_route_deviation_threshold))
    diagnostics.target_near_margin = max(0.0, float(nav_config.coordinate_target_near_margin))
    diagnostics.target_stall_ms = max(0, int(nav_config.coordinate_target_stall_ms))
    diagnostics.throttle_ms = max(0, int(nav_config.coordinate_diagnostics_throttle_ms))
    diagnostics.recovery_enabled = bool(nav_config.coordinate_recovery_enabled)
    diagnostics.recovery_score_threshold = max(1, int(nav_config.coordinate_recovery_score_threshold))
    diagnostics.recovery_window_ms = max(100, int(nav_config.coordinate_recovery_window_ms))
    diagnostics.recovery_cooldown_ms = max(0, int(nav_config.coordinate_recovery_cooldown_ms))
    diagnostics.recovery_timeout_ms = max(100, int(nav_config.coordinate_recovery_timeout_ms))
    diagnostics.long_f2f_tracking_ms = max(0, int(nav_config.coordinate_long_f2f_tracking_ms))
    diagnostics.localization_sample_interval_ms = max(0, int(nav_config.coordinate_localization_sample_interval_ms))
    diagnostics.visual_mismatch_threshold = max(0.0, float(nav_config.coordinate_visual_mismatch_threshold))
    diagnostics.visual_mismatch_required_frames = max(1, int(nav_config.coordinate_visual_mismatch_frames))

    navigation_task_controller.arrival_radius = max(4.0, float(nav_config.required_arrival_radius))
    navigation_task_controller.required_progress_margin = max(
        0.0,
        float(nav_config.route_anchor_target_margin),
    )
    if getattr(navigation_task_controller, "builder", None) is not None:
        navigation_task_controller.builder.required_arrival_radius = navigation_task_controller.arrival_radius
    if getattr(navigation_task_controller, "scheduler", None) is not None:
        scheduler = navigation_task_controller.scheduler
        scheduler.event_route_backtrack_margin = max(0.0, float(nav_config.event_route_backtrack_margin))
        scheduler.event_required_forward_margin = max(0.0, float(nav_config.event_required_forward_margin))
        scheduler.event_exit_forward_margin = max(0.0, float(nav_config.event_exit_forward_margin))
        scheduler.event_fallback_player_radius = max(0.0, float(nav_config.event_fallback_player_radius))
        scheduler.event_fallback_static_margin = max(0.0, float(nav_config.event_fallback_static_margin))

    movement = navigation_task_controller.movement
    movement.click_cooldown_ms = max(120, int(nav_config.auto_click_cooldown_ms))
    movement.min_click_target_delta = max(0.0, float(nav_config.auto_min_click_target_delta))
    movement.arrival_radius = navigation_task_controller.arrival_radius
    movement.anchor_arrival_radius = max(4.0, float(nav_config.anchor_arrival_radius))
    movement.route_anchor_target_margin = max(0.0, float(nav_config.route_anchor_target_margin))
    movement.exact_goal_click_enabled = bool(nav_config.exact_goal_click_enabled)
    movement.exact_goal_click_radius = max(0.0, float(nav_config.exact_goal_click_radius))
    movement.exact_goal_click_cooldown_ms = max(0, int(nav_config.exact_goal_click_cooldown_ms))
    movement.exact_goal_recovery_suppress_ms = max(0, int(nav_config.exact_goal_recovery_suppress_ms))
    movement.replan_throttle_ms = max(0, int(nav_config.movement_replan_throttle_ms))
    movement.fallback_replan_interval_ms = max(0, int(nav_config.fallback_replan_interval_ms))
    movement.progress_timeout_ms = max(200, int(nav_config.movement_progress_timeout_ms))
    movement.min_progress_delta = max(0.0, float(nav_config.movement_min_progress_delta))
    movement.max_recover_attempts = max(0, int(nav_config.movement_max_recover_attempts))
    movement.path_deviation_threshold = max(8.0, float(nav_config.movement_path_deviation_threshold))
    movement.local_probe_forward_distance = max(0.0, float(nav_config.local_probe_forward_distance))
    movement.local_probe_lateral_distance = max(0.0, float(nav_config.local_probe_lateral_distance))
    movement.recovery_probe_forward_min = max(0.0, float(nav_config.recovery_probe_forward_min))
    movement.recovery_probe_forward_max = max(
        movement.recovery_probe_forward_min,
        float(nav_config.recovery_probe_forward_max),
    )
    movement.recovery_probe_forward_multiplier = max(0.0, float(nav_config.recovery_probe_forward_multiplier))
    movement.recovery_probe_lateral_distance = max(0.0, float(nav_config.recovery_probe_lateral_distance))
    navigation_task_controller.event_approach.configure(
        enabled=bool(nav_config.event_approach_enabled),
        game_view_map_size=max(100, int(nav_config.game_view_map_size)),
        visible_margin=max(0, int(nav_config.event_visible_margin)),
        approach_lookahead=max(8.0, float(nav_config.event_approach_lookahead)),
        click_cooldown_ms=max(120, int(nav_config.event_approach_click_cooldown_ms)),
        stop_radius=max(4.0, float(nav_config.event_stop_radius)),
        settle_ms=max(0, int(nav_config.event_settle_ms)),
        stable_frames=max(1, int(nav_config.event_stable_frames)),
        max_motion_per_frame=max(0.0, float(nav_config.event_max_motion_per_frame)),
    )
