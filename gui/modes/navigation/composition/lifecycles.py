from __future__ import annotations

from PySide6.QtCore import QTimer

from ..calibration import (
    NavigationScreenCalibrationLifecycle,
    NavigationScreenCalibrationLifecycleTargets,
)
from ..config import NavigationConfigLifecycle, NavigationConfigLifecycleTargets
from ..display import NavigationMapDisplayLifecycle
from ..events import (
    ManualEventTestController,
    NavigationEventDialogLifecycle,
    NavigationEventDialogLifecycleTargets,
    NavigationEventLifecycle,
    NavigationEventLifecycleTargets,
)
from ..map import (
    MISSING_MAP_DATA_LABEL,
    NavigationMapClickLifecycle,
    NavigationMapClickLifecycleTargets,
    NavigationMapLoadLifecycle,
    NavigationMapLoadLifecycleTargets,
)
from ..route import NavigationRouteLifecycle, NavigationRouteLifecycleTargets
from ..runtime import (
    NavigationRuntimeCommandLifecycle,
    NavigationRuntimeCommandLifecycleTargets,
    NavigationRuntimeFrameLoop,
)
from ..sampling import NavigationSampleCaptureLifecycle, NavigationSampleCaptureLifecycleTargets


def initialize_navigation_pre_signal_lifecycles(owner) -> None:
    """Create lifecycle objects that must exist before Qt signal wiring."""
    owner.display_lifecycle = NavigationMapDisplayLifecycle(owner)
    owner.event_dialog_lifecycle = NavigationEventDialogLifecycle(
        NavigationEventDialogLifecycleTargets(
            parent=owner,
            main_window=owner.main_window,
            get_event_dialog=lambda: owner.event_dialog,
            set_event_dialog=lambda dialog: setattr(owner, "event_dialog", dialog),
            get_portal_test_controller=lambda: getattr(owner, "portal_test_controller", None),
            get_event_registry=lambda: owner.event_registry,
            get_event_config=lambda: owner.event_config,
            get_event_coordinator=lambda: owner.event_coordinator,
            get_map_name=lambda: owner.map_combo.currentText() if owner.map_combo else "",
            on_config_changed=owner._on_event_config_changed,
            on_save_requested=owner._save_event_config,
            on_test_portal_requested=owner._run_portal_manual_test,
            on_reset_portal_requested=owner._reset_portal_event_state,
            on_reset_events_requested=owner._reset_event_state,
        )
    )
    owner.route_lifecycle = NavigationRouteLifecycle(
        NavigationRouteLifecycleTargets(
            parent=owner,
            status_label=owner.status_label,
            route_editor=owner.route_editor,
            route_panel=owner.route_panel,
            navigation_task_controller=owner.navigation_task_controller,
            get_map_folder_path=lambda: owner.map_folder_path,
            set_route_data=lambda route_data: setattr(owner, "route_data", route_data),
            render_route_overlay=owner._render_route_overlay,
        )
    )
    owner.config_lifecycle = NavigationConfigLifecycle(
        NavigationConfigLifecycleTargets(
            parent=owner,
            source_file=owner.source_file,
            nav_status_label=owner.params_dialog.nav_status_label,
            path_finder=owner.app_context.path_finder,
            motion_controller=owner.motion_controller,
            navigation_task_controller=owner.navigation_task_controller,
            get_nav_config=lambda: owner.nav_config,
            set_nav_config=lambda config: setattr(owner, "nav_config", config),
            get_nav_core=lambda: owner.nav_core,
            get_map_folder_path=lambda: owner.map_folder_path,
            reset_capture_center=lambda: setattr(owner, "_capture_center_physical", None),
            update_overlay_display=owner._update_overlay_display,
            refresh_game_view_rect_from_known_position=owner._refresh_game_view_rect_from_known_position,
        )
    )
    owner.screen_calibration_lifecycle = NavigationScreenCalibrationLifecycle(
        NavigationScreenCalibrationLifecycleTargets(
            parent=owner,
            controller=owner.screen_center_calibration,
            params_dialog=owner.params_dialog,
            get_nav_config=lambda: owner.nav_config,
            set_center_selector=lambda selector: setattr(owner, "center_selector", selector),
            update_overlay_display=owner._update_overlay_display,
            save_nav_config=owner._save_nav_config,
        )
    )
    owner.map_load_lifecycle = NavigationMapLoadLifecycle(
        NavigationMapLoadLifecycleTargets(
            parent=owner,
            source_file=owner.source_file,
            missing_label=MISSING_MAP_DATA_LABEL,
            params_dialog=owner.params_dialog,
            start_button=owner.btn_start,
            hint_button=owner.btn_hint,
            route_panel=owner.route_panel,
            status_label=owner.status_label,
            compute_scale=owner._compute_scale,
            set_map_session=owner._set_loaded_map_session,
            apply_config_to_runtime=owner._apply_config_to_core,
            load_route_data=owner.load_route_data,
            initialize_event_system=owner._initialize_event_system,
            render_map=owner._render_map,
            show_last_exit_position=owner._show_last_exit_position,
            render_route_overlay=owner._render_route_overlay,
        )
    )
    owner.sample_capture_lifecycle = NavigationSampleCaptureLifecycle(
        NavigationSampleCaptureLifecycleTargets(
            parent=owner,
            main_window=owner.main_window,
            status_label=owner.status_label,
            get_map_name=lambda: owner.map_combo.currentText() if owner.map_combo else "",
            is_ready=lambda: owner.map_folder_path is not None and owner.nav_config is not None,
            capture_sample=owner.capture_minimap_sample,
        )
    )


def initialize_navigation_runtime_lifecycles(owner) -> None:
    """Create timer-bound runtime, event, map-click, and frame-loop lifecycles."""
    owner.nav_timer = QTimer()
    owner.nav_timer.timeout.connect(owner.navigation_loop)
    owner._ensure_event_dialog()
    owner.portal_test_controller = ManualEventTestController(
        owner.event_dialog.test_portal_button if owner.event_dialog else None,
        "测试传送门",
        "停止传送门测试",
    )
    owner.command_lifecycle = NavigationRuntimeCommandLifecycle(
        NavigationRuntimeCommandLifecycleTargets(
            parent=owner,
            status_label=owner.status_label,
            start_button=owner.btn_start,
            auto_navigation_button=owner.btn_auto_nav,
            nav_timer=owner.nav_timer,
            motion_controller=owner.motion_controller,
            navigation_task_controller=owner.navigation_task_controller,
            game_input_window_mode=owner.game_input_window_mode,
            portal_test_controller=owner.portal_test_controller,
            get_map_folder_path=lambda: owner.map_folder_path,
            get_nav_core=lambda: owner.nav_core,
            get_nav_config=lambda: owner.nav_config,
            get_route_data=lambda: owner.route_data,
            get_tracker=lambda: owner.app_context.tracker,
            get_auto_navigation_enabled=lambda: owner.auto_navigation_enabled,
            set_auto_navigation_enabled=lambda enabled: setattr(owner, "auto_navigation_enabled", enabled),
            set_current_player_local_pos=lambda value: setattr(owner, "_current_player_local_pos", value),
            use_unified_navigation_loop=owner._use_unified_navigation_loop,
            apply_config_to_runtime=owner._apply_config_to_core,
            stop_portal_manual_test=lambda reason: owner._set_portal_manual_test_active(False, reason=reason),
            render_route_overlay=owner._render_route_overlay,
            start_event_observer=owner._start_event_async_observer,
            stop_event_observer=owner._stop_event_async_observer,
        )
    )
    owner.event_lifecycle = NavigationEventLifecycle(
        NavigationEventLifecycleTargets(
            parent=owner,
            status_label=owner.status_label,
            start_button=owner.btn_start,
            nav_timer=owner.nav_timer,
            motion_controller=owner.motion_controller,
            navigation_task_controller=owner.navigation_task_controller,
            portal_test_controller=owner.portal_test_controller,
            get_map_folder_path=lambda: owner.map_folder_path,
            get_event_config=lambda: owner.event_config,
            get_event_coordinator=lambda: owner.event_coordinator,
            get_nav_core=lambda: owner.nav_core,
            get_nav_config=lambda: owner.nav_config,
            get_route_data=lambda: owner.route_data,
            get_auto_navigation_enabled=lambda: owner.auto_navigation_enabled,
            toggle_navigation=owner.toggle_navigation,
            set_game_input_window_mode=owner._set_game_input_window_mode,
            refresh_event_dialog=owner._refresh_event_dialog,
            discard_async_event_results=owner._discard_async_event_results,
            clear_event_overlay=owner._clear_event_overlay,
            render_event_overlay=owner._render_event_overlay,
            refresh_event_dialog_tasks=owner._refresh_event_dialog_tasks,
        )
    )
    owner.map_click_lifecycle = NavigationMapClickLifecycle(
        NavigationMapClickLifecycleTargets(
            parent=owner,
            view=owner.view,
            scene=owner.scene,
            status_label=owner.status_label,
            hint_button=owner.btn_hint,
            motion_controller=owner.motion_controller,
            route_editor=owner.route_editor,
            get_nav_core=lambda: owner.nav_core,
            get_map_folder_path=lambda: owner.map_folder_path,
            set_route_data=lambda route_data: setattr(owner, "route_data", route_data),
            get_hint_item=lambda: owner.hint_item,
            set_hint_item=lambda item: setattr(owner, "hint_item", item),
            get_target_item=lambda: owner.target_item,
            render_route_overlay=owner._render_route_overlay,
            set_map_click_mode=owner._set_map_click_mode,
            update_monitor_rect=owner._update_monitor_rect,
            update_game_view_rect=owner._update_game_view_rect,
        )
    )
    owner.runtime_frame_loop = NavigationRuntimeFrameLoop(owner)
