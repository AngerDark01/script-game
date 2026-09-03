"""
导航模式模块 - 提供游戏内自动导航功能的主界面

本模块实现了基于地图匹配的玩家位置实时定位和导航功能，
支持手动设置初始位置、自动路径跟踪、屏幕中心校准等功能。
"""

import time
from pathlib import Path

from PySide6.QtWidgets import QMessageBox, QWidget

from core.events.async_observer import AsyncEventObserver
from core.navigation_tasks.controller import NavigationTaskController
from core.input import MotionController
from core.routing import RouteManager
from core.events.debug import event_log
from ...selection.indicator_overlay import OverlayWindow
from ...dialogs.event_manager_dialog import EventManagerDialog
from ...dialogs.nav_params_dialog import NavParametersDialog
from ...navigation_params import NavConfig
from .calibration import ScreenCenterCalibrationController, screen_scale
from .composition import (
    initialize_navigation_pre_signal_lifecycles,
    initialize_navigation_runtime_lifecycles,
)
from .event_adapter import (
    build_event_tick,
    create_default_event_registry,
    find_default_game_window_rect,
)
from .input import GameInputWindowMode
from .map import (
    MISSING_MAP_DATA_LABEL,
    build_capture_geometry,
    list_map_names,
    handle_navigation_map_event_filter,
    physical_center_from_logical,
)
from .events import (
    initialize_navigation_event_system,
    summarize_event_config,
)
from .hooks import NavigationHookRuntime
from .route import RouteEditor
from .presentation import (
    populate_map_combo,
    show_owned_dialog,
    toggle_owned_dialog,
    update_debug_overlay,
    warn_overlay_map_config_incomplete,
)
from .runtime.minimap_sample_capture import (
    capture_current_minimap_frame,
    save_minimap_sample,
)
from .ui import build_navigation_ui, connect_navigation_signals


class NavigationModeWidget(QWidget):
    """
    导航模式主窗口组件

    提供完整的导航功能界面，包括：
    - 地图加载和显示
    - 玩家实时位置定位
    - 导航参数配置
    - 自动移动控制
    - 屏幕中心校准
    """

    def __init__(self, app_context, main_window):
        """Initialize the navigation page composition root."""
        super().__init__()
        self.app_context = app_context
        self.main_window = main_window
        self.nav_core = None
        self.motion_controller = MotionController()
        self.overlay = OverlayWindow()
        self.screen_center_calibration = ScreenCenterCalibrationController()
        self.center_selector = None
        self.nav_config = NavConfig()
        self.map_folder_path = None
        self.params_dialog = NavParametersDialog(self)
        self.event_dialog = None

        self._capture_center_physical = None
        self._current_capture_rect = None
        self._current_player_local_pos = None
        self._latest_minimap_frame = None
        self._latest_minimap_capture_rect = None
        self._latest_minimap_player_local_pos = None
        self.route_manager = RouteManager()
        self.route_editor = RouteEditor(self.route_manager)
        self.route_panel = None
        self.route_data = None
        self.navigation_task_controller = NavigationTaskController()
        self.auto_navigation_enabled = False
        self.route_overlay_items = []
        self.route_path_item = None
        self.game_view_rect_item = None
        self.game_input_window_mode = GameInputWindowMode(main_window)
        self.hook_runtime = NavigationHookRuntime(
            navigation_task_controller=self.navigation_task_controller,
            motion_controller=self.motion_controller,
            enable_game_input_mode=lambda: self._set_game_input_window_mode(True),
        )
        self.event_registry = create_default_event_registry()
        self.event_config = None
        self.event_coordinator = None
        self.event_async_observer = None
        self.event_capture_provider = None
        self.event_overlay_items = []
        self._event_arbitration_last_log_ms = 0
        self.source_file = __file__

        self.init_ui()
        initialize_navigation_pre_signal_lifecycles(self)
        self._connect_signals()
        initialize_navigation_runtime_lifecycles(self)

    def init_ui(self):
        """Build controls and scene items for the navigation page."""
        build_navigation_ui(self)

    def _connect_signals(self):
        """Wire controls and child dialog signals to widget slots."""
        connect_navigation_signals(self)

    def _ensure_event_dialog(self) -> EventManagerDialog:
        return self.event_dialog_lifecycle.ensure_dialog()

    def _connect_event_dialog_signals(self) -> None:
        self.event_dialog_lifecycle.connect_signals()

    def toggle_params_dialog(self):
        """Toggle the navigation parameter dialog."""
        if self._toggle_owned_dialog(self.params_dialog):
            self.params_dialog.hide()

    def toggle_event_dialog(self):
        self.event_dialog_lifecycle.toggle_dialog()

    def _toggle_owned_dialog(self, dialog) -> bool:
        """Show child dialogs above the main UI; return True only when caller should hide."""
        return toggle_owned_dialog(dialog, self.main_window)

    def _show_owned_dialog(self, dialog) -> None:
        show_owned_dialog(dialog, self.main_window)

    def _set_map_click_mode(self, mode: str):
        self.route_panel.set_click_mode(mode)

    def toggle_exit_mode(self):
        self.route_panel.toggle_exit_mode(self.map_folder_path)

    def toggle_guide_mode(self):
        self.route_panel.toggle_guide_mode(self.map_folder_path)

    def toggle_required_mode(self):
        self.route_panel.toggle_required_mode(self.map_folder_path)

    def _set_route_buttons_enabled(self, enabled: bool):
        self.route_panel.set_buttons_enabled(enabled)

    def load_route_data(self):
        return self.route_lifecycle.load_route_data()

    def save_route(self):
        self.route_lifecycle.save_route()

    def undo_guide_point(self):
        self.route_lifecycle.undo_guide_point()

    def undo_required_point(self):
        self.route_lifecycle.undo_required_point()

    def clear_route(self):
        self.route_lifecycle.clear_route()

    def _clear_route_overlay(self):
        self.display_lifecycle.clear_route_overlay()

    def _clear_event_overlay(self):
        self.display_lifecycle.clear_event_overlay()

    def _global_to_scene(self, point):
        return self.display_lifecycle.global_to_scene(point)

    def _render_event_overlay(self):
        self.display_lifecycle.render_event_overlay()

    def _render_route_overlay(
        self,
        current_path=None,
        current_subgoal=None,
        current_required_index=None,
        current_guide_index=None,
        current_target_kind=None,
    ):
        self.display_lifecycle.render_route_overlay(
            current_path=current_path,
            current_subgoal=current_subgoal,
            current_required_index=current_required_index,
            current_guide_index=current_guide_index,
            current_target_kind=current_target_kind,
        )

    def _can_start_auto_navigation(self):
        return self.command_lifecycle.can_start_auto_navigation()

    def _set_game_input_window_mode(self, enabled: bool):
        """Keep the tool window from covering the game while auto navigation clicks."""
        self.command_lifecycle.set_game_input_window_mode(enabled)

    def toggle_auto_navigation(self):
        self.command_lifecycle.toggle_auto_navigation()

    def refresh_map_list(self):
        """Refresh available navigation maps from map_data."""
        dirs = list_map_names(__file__)
        populate_map_combo(self.map_combo, dirs, MISSING_MAP_DATA_LABEL)

    def load_map(self):
        """Load the selected map through the map lifecycle facade."""
        map_name = self.map_combo.currentText()
        self.map_load_lifecycle.load_selected_map(map_name)

    def _set_loaded_map_session(self, map_session):
        self.map_folder_path = map_session.map_folder_path
        self.nav_config = map_session.nav_config
        self.nav_core = map_session.nav_core
        self._capture_center_physical = map_session.capture_center_physical
        if hasattr(self, "sample_window_button"):
            self.sample_window_button.setEnabled(True)
        if hasattr(self, "save_minimap_sample_button"):
            self.save_minimap_sample_button.setEnabled(True)
        if hasattr(self, "sample_capture_lifecycle"):
            self.sample_capture_lifecycle.update_ready_state()

    def _initialize_event_system(self):
        self._stop_event_async_observer()
        runtime = initialize_navigation_event_system(
            map_folder_path=self.map_folder_path,
            event_registry=self.event_registry,
            screen_capture=self.app_context.screen_capture,
            window_finder=self._find_game_window_rect,
            map_name=self.map_combo.currentText() if self.map_combo else "",
            refresh_event_dialog=self._refresh_event_dialog,
        )
        self.event_config = runtime.event_config
        self.event_coordinator = runtime.event_coordinator
        self.event_capture_provider = runtime.event_capture_provider
        self._start_event_async_observer()
        self.hook_runtime.apply_event_config(self.event_config)
        self._refresh_event_dialog()

    def _refresh_event_dialog(self):
        self.event_dialog_lifecycle.refresh_dialog()

    def _on_event_config_changed(self, event_config):
        self.event_config = event_config
        if self.event_coordinator:
            self.event_coordinator.config = event_config
        self.hook_runtime.apply_event_config(event_config)
        self._clear_event_overlay()
        event_log(
            "event config changed",
            enabled=bool(getattr(event_config, "enabled", True)),
            events=summarize_event_config(event_config),
        )

    def _start_event_async_observer(self) -> None:
        if self.event_coordinator is None:
            return
        if self.event_async_observer is not None:
            return
        self.event_async_observer = AsyncEventObserver(self.event_coordinator)

    def _stop_event_async_observer(self) -> None:
        observer = getattr(self, "event_async_observer", None)
        if observer is None:
            return
        observer.stop()
        self.event_async_observer = None

    def _discard_async_event_results(self, reason: str = "") -> None:
        observer = getattr(self, "event_async_observer", None)
        if observer is None:
            return
        observer.discard_pending_and_result(reason or "event state reset")

    def _save_event_config(self):
        self.event_lifecycle.save_event_config()

    def _reset_portal_event_state(self):
        self.event_lifecycle.reset_portal_event_state(now_ms=int(time.time() * 1000))

    def _reset_event_state(self):
        self.event_lifecycle.reset_event_state(now_ms=int(time.time() * 1000))

    def _find_game_window_rect(self):
        return find_default_game_window_rect()

    def _build_event_tick(self, now_ms, frame, player_pos, localized_pos, conf):
        return build_event_tick(
            now_ms=now_ms,
            frame=frame,
            player_pos=player_pos,
            localized_pos=localized_pos,
            confidence=conf,
            nav_core=self.nav_core,
            nav_config=self.nav_config,
            map_name=self.map_combo.currentText() if self.map_combo else "",
            capture_provider=self.event_capture_provider,
        )

    def _reset_event_move_runtime(self):
        self.event_lifecycle.reset_event_move_runtime()

    def _run_portal_manual_test(self):
        self.event_lifecycle.run_portal_manual_test()

    def _set_portal_manual_test_active(self, active: bool, reason: str = "") -> None:
        self.event_lifecycle.set_portal_manual_test_active(active, reason=reason)

    def _refresh_event_dialog_tasks(self):
        self.event_dialog_lifecycle.refresh_tasks()

    def _render_map(self):
        """Render the loaded map and reset scene item references."""
        self.display_lifecycle.render_map()

    def _build_capture_geometry(self):
        """根据当前配置返回真实截图矩形和玩家在截图中的相对位置。"""
        if not self.nav_config:
            return None, None

        if self._capture_center_physical is None and self.nav_config.monitor_logical_center:
            sx, sy = self._compute_scale()
            self._capture_center_physical = physical_center_from_logical(
                self.nav_config.monitor_logical_center,
                (sx, sy),
            )
        rect, player_pos, self._capture_center_physical = build_capture_geometry(
            self.nav_config,
            self._capture_center_physical,
        )
        return rect, player_pos

    def toggle_minimap_sample_window(self):
        """Show or hide the floating minimap sample capture window."""
        self.sample_capture_lifecycle.toggle_window()

    def capture_minimap_sample(self):
        """Capture and persist one current minimap monitor frame."""
        frame = self._latest_minimap_frame
        capture_rect = self._latest_minimap_capture_rect
        player_pos = self._latest_minimap_player_local_pos or self._current_player_local_pos
        source = "latest_frame"

        if frame is None or capture_rect is None:
            frame, capture_rect, player_pos = capture_current_minimap_frame(
                build_capture_geometry=self._build_capture_geometry,
                screen_capture=self.app_context.screen_capture,
            )
            source = "manual_capture"

        result = save_minimap_sample(
            project_root=Path(__file__).resolve().parents[3],
            map_name=self.map_combo.currentText() if self.map_combo else "",
            frame=frame,
            capture_rect=capture_rect,
            monitor_size=getattr(self.nav_config, "monitor_size", None),
            player_local_pos=player_pos,
            source=source,
        )
        if hasattr(self, "sample_capture_lifecycle"):
            self.sample_capture_lifecycle.show_result(result)
        return result

    def save_minimap_sample(self):
        """Save one current minimap monitor frame for detector samples."""
        result = self.capture_minimap_sample()
        if result.ok:
            self.status_label.setText(result.message)
            return
        QMessageBox.warning(self, "小地图样本", result.message)

    def _update_overlay_display(self):
        """根据当前配置实时更新屏幕幕布显示。"""
        if not self.params_dialog.nav_toggle_overlay_btn.isChecked():
            return

        capture_rect, _ = self._build_capture_geometry()
        update_debug_overlay(
            self.overlay,
            capture_rect=capture_rect,
            nav_config=self.nav_config,
            scale=self._compute_scale(),
        )

    def _update_monitor_rect(self, player_pos, capture_rect=None, player_local_pos=None):
        """Update the green minimap capture rectangle."""
        self.display_lifecycle.update_monitor_rect(
            player_pos,
            capture_rect=capture_rect,
            player_local_pos=player_local_pos,
        )

    def _update_game_view_rect(self, player_pos):
        """Update the orange real-game-view rectangle in map coordinates."""
        self.display_lifecycle.update_game_view_rect(player_pos)

    def _refresh_game_view_rect_from_known_position(self):
        """Refresh the orange rectangle immediately after display-related params change."""
        self.display_lifecycle.refresh_game_view_rect_from_known_position()

    def _show_last_exit_position(self):
        """Show the drawing-mode saved position marker from the loaded map."""
        self.display_lifecycle.show_last_exit_position()

    def _apply_config_to_core(self):
        """Apply the current NavConfig to runtime services."""
        self.config_lifecycle.apply_to_runtime()

    def _on_parameter_changed(self, new_config: NavConfig):
        """Handle parameter dialog changes without immediately saving them."""
        self.config_lifecycle.handle_parameter_changed(new_config)

    def _configure_navigation_task_controller(self):
        self.config_lifecycle.configure_task_controller()

    def _save_nav_config(self):
        """Save the current map navigation config."""
        self.config_lifecycle.save_current_map_config()

    def _save_nav_default_config(self):
        self.config_lifecycle.save_default_config()

    def _compute_scale(self):
        """Return the logical-to-physical screen scale."""
        return screen_scale()

    def _toggle_overlay_display(self):
        """Toggle the debug capture overlay."""
        if not self.nav_config or (not self.nav_config.monitor_logical_center and not self.nav_config.monitor_region):
            self.params_dialog.nav_toggle_overlay_btn.setChecked(False)
            warn_overlay_map_config_incomplete(self)
            return

        if self.params_dialog.nav_toggle_overlay_btn.isChecked():
            self._update_overlay_display()
        else:
            self.overlay.hide_overlay()

    def eventFilter(self, watched, event):
        """Keep the Qt event-filter entry point and delegate map scene clicks."""
        if handle_navigation_map_event_filter(
            watched=watched,
            event=event,
            scene=self.scene,
            handle_map_click=self.handle_map_click,
        ):
            return True
        return super().eventFilter(watched, event)

    def handle_map_click(self, pos):
        """Handle map clicks for hint placement, route editing, or manual movement."""
        self.map_click_lifecycle.handle_map_click(pos)

    def set_initial_hint(self, scene_pos):
        """Set the initial localization hint through the map click lifecycle."""
        self.map_click_lifecycle.set_initial_hint(scene_pos)

    def toggle_hint_mode(self):
        """Toggle initial-hint click mode."""
        self.map_click_lifecycle.toggle_hint_mode()

    def _calibrate_screen_center(self):
        """Start screen-center calibration."""
        self.screen_calibration_lifecycle.start_screen_center_calibration()

    def _handle_calibration_click(self, x, y):
        """Apply a screen-center calibration click."""
        self.screen_calibration_lifecycle.handle_screen_center_click(x, y)


    def toggle_navigation(self):
        """Toggle navigation runtime through the command lifecycle."""
        self.command_lifecycle.toggle_navigation()

    def stop_runtime(self) -> None:
        """Stop navigation side effects idempotently without toggling the UI command."""
        self.command_lifecycle.stop_runtime()
        self._stop_event_async_observer()

    def _use_unified_navigation_loop(self) -> None:
        try:
            self.nav_timer.timeout.disconnect(self.navigation_loop)
        except (TypeError, RuntimeError):
            pass
        try:
            self.nav_timer.timeout.disconnect(self._navigation_loop_unified)
        except (TypeError, RuntimeError):
            pass
        self.nav_timer.timeout.connect(self._navigation_loop_unified)

    def _navigation_loop_unified(self):
        """Unified navigation loop: event observation + one task controller."""
        self.runtime_frame_loop.run()

    def navigation_loop(self):
        """Compatibility entry point for the Qt timer; all logic lives in the unified loop."""
        return self._navigation_loop_unified()
