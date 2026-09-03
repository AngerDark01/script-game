from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from core.events.debug import start_event_log_session

from ..presentation import (
    show_auto_navigation_started,
    show_auto_navigation_stopped,
    show_navigation_paused,
    show_navigation_started,
    warn_auto_navigation_invalid_route,
    warn_auto_navigation_unavailable,
    warn_navigation_map_config_incomplete,
    warn_navigation_missing_screen_center,
)


@dataclass(frozen=True)
class NavigationRuntimeCommandLifecycleTargets:
    parent: object
    status_label: object
    start_button: object
    auto_navigation_button: object
    nav_timer: object
    motion_controller: object
    navigation_task_controller: object
    game_input_window_mode: object
    portal_test_controller: object
    get_map_folder_path: Callable[[], str | None]
    get_nav_core: Callable[[], object]
    get_nav_config: Callable[[], object]
    get_route_data: Callable[[], dict | None]
    get_tracker: Callable[[], object]
    get_auto_navigation_enabled: Callable[[], bool]
    set_auto_navigation_enabled: Callable[[bool], None]
    set_current_player_local_pos: Callable[[object], None]
    use_unified_navigation_loop: Callable[[], None]
    apply_config_to_runtime: Callable[[], object]
    stop_portal_manual_test: Callable[[str], None]
    render_route_overlay: Callable[[], None]
    start_event_observer: Callable[[], None]
    stop_event_observer: Callable[[], None]


class NavigationRuntimeCommandLifecycle:
    """Own navigation start/stop and auto-navigation command state transitions."""

    def __init__(self, targets: NavigationRuntimeCommandLifecycleTargets) -> None:
        self.targets = targets

    def can_start_auto_navigation(self) -> tuple[bool, str]:
        nav_config = self.targets.get_nav_config()
        if not self.targets.get_map_folder_path() or not self.targets.get_nav_core():
            return False, "请先加载地图"
        main = self._main_route()
        if not main.get("exit_region"):
            return False, "请先设置出口"
        if not nav_config or not nav_config.game_screen_center:
            return False, "请先校准屏幕中心"
        if self._navigation_capture_config_incomplete(nav_config):
            return False, "缺少监视窗口配置"
        return True, ""

    def set_game_input_window_mode(self, enabled: bool) -> None:
        self.targets.game_input_window_mode.set_enabled(enabled)

    def toggle_auto_navigation(self) -> None:
        if self.targets.auto_navigation_button.isChecked():
            self._start_auto_navigation()
        else:
            self._stop_auto_navigation()

    def toggle_navigation(self) -> None:
        if self.targets.start_button.isChecked():
            self.start_navigation()
        else:
            self.stop_runtime()

    def start_navigation(self) -> bool:
        self.targets.use_unified_navigation_loop()
        print("DEBUG: '开始导航' button clicked.")
        start_event_log_session("navigation")

        nav_config = self.targets.get_nav_config()
        if not nav_config or not nav_config.game_screen_center:
            warn_navigation_missing_screen_center(self.targets.parent)
            self.targets.start_button.setChecked(False)
            return False

        if self._navigation_capture_config_incomplete(nav_config):
            warn_navigation_map_config_incomplete(self.targets.parent)
            self.targets.start_button.setChecked(False)
            return False

        self.targets.apply_config_to_runtime()
        self.targets.set_current_player_local_pos(None)
        self.targets.start_event_observer()

        nav_core = self.targets.get_nav_core()
        if nav_core:
            nav_core.request_full_map_localization("navigation_start")

        tracker = self.targets.get_tracker()
        if tracker:
            tracker.reset()

        interval = 1000 // nav_config.fps
        print("DEBUG: Navigation observation mode started; input remains disabled until auto navigation starts.")
        self.targets.motion_controller.set_control_enabled(False)
        self.targets.nav_timer.start(interval)
        self.targets.start_button.setText("停止导航")
        show_navigation_started(self.targets.status_label)
        print("DEBUG: Navigation started.")
        return True

    def stop_runtime(self) -> None:
        print("DEBUG: Stopping navigation runtime.")
        self.targets.nav_timer.stop()
        self.targets.stop_event_observer()
        print("DEBUG: Disabling motion_controller.")
        self.targets.motion_controller.set_control_enabled(False)

        nav_core = self.targets.get_nav_core()
        if nav_core:
            nav_core.is_first_frame_localized = False

        self.targets.set_auto_navigation_enabled(False)
        if getattr(self.targets.portal_test_controller, "active", False):
            self.targets.stop_portal_manual_test("navigation stopped")

        self.targets.navigation_task_controller.stop()
        self.set_game_input_window_mode(False)
        self.targets.start_button.setChecked(False)
        self.targets.auto_navigation_button.setChecked(False)
        self.targets.render_route_overlay()
        self.targets.start_button.setText("开始导航")
        show_navigation_paused(self.targets.status_label)
        print("DEBUG: Navigation stopped.")

    def _start_auto_navigation(self) -> None:
        ok, message = self.can_start_auto_navigation()
        if not ok:
            self.targets.auto_navigation_button.setChecked(False)
            warn_auto_navigation_unavailable(self.targets.parent, message)
            return

        self.targets.navigation_task_controller.load_route(self._main_route())
        if not self.targets.navigation_task_controller.start():
            self.targets.auto_navigation_button.setChecked(False)
            warn_auto_navigation_invalid_route(self.targets.parent)
            return

        if not self.targets.nav_timer.isActive():
            self.targets.start_button.setChecked(True)
            self.toggle_navigation()
            if not self.targets.nav_timer.isActive():
                self.targets.navigation_task_controller.stop()
                self.targets.set_auto_navigation_enabled(False)
                self.targets.auto_navigation_button.setChecked(False)
                return

        self.targets.set_auto_navigation_enabled(True)
        self.set_game_input_window_mode(True)
        show_auto_navigation_started(self.targets.status_label)

    def _stop_auto_navigation(self) -> None:
        self.targets.set_auto_navigation_enabled(False)
        self.targets.navigation_task_controller.stop()
        self.set_game_input_window_mode(False)
        self.targets.render_route_overlay()
        show_auto_navigation_stopped(self.targets.status_label)

    def _main_route(self) -> dict:
        return (self.targets.get_route_data() or {}).get("routes", {}).get("main", {})

    @staticmethod
    def _navigation_capture_config_incomplete(nav_config) -> bool:
        return (
            not nav_config
            or (not nav_config.monitor_logical_center and not nav_config.monitor_region)
            or not nav_config.monitor_size
        )
