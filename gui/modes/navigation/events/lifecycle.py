from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from core.events.config import save_event_config
from core.events.debug import event_log, start_event_log_session

from ..presentation import (
    show_event_config_save_failed,
    show_event_config_saved,
    show_event_state_reset,
    show_portal_manual_test_started,
    show_portal_manual_test_stopped,
    warn_event_config_missing,
    warn_event_system_missing,
    warn_portal_manual_test_missing_screen_center,
)


@dataclass(frozen=True)
class NavigationEventLifecycleTargets:
    parent: object
    status_label: object
    start_button: object
    nav_timer: object
    motion_controller: object
    navigation_task_controller: object
    portal_test_controller: object
    get_map_folder_path: Callable[[], str | None]
    get_event_config: Callable[[], object]
    get_event_coordinator: Callable[[], object]
    get_nav_core: Callable[[], object]
    get_nav_config: Callable[[], object]
    get_route_data: Callable[[], dict | None]
    get_auto_navigation_enabled: Callable[[], bool]
    toggle_navigation: Callable[[], None]
    set_game_input_window_mode: Callable[[bool], None]
    refresh_event_dialog: Callable[[], None]
    discard_async_event_results: Callable[[str], None]
    clear_event_overlay: Callable[[], None]
    render_event_overlay: Callable[[], None]
    refresh_event_dialog_tasks: Callable[[], None]


class NavigationEventLifecycle:
    """Own event config save and portal manual-test runtime transitions."""

    def __init__(self, targets: NavigationEventLifecycleTargets) -> None:
        self.targets = targets

    def save_event_config(self) -> bool:
        map_folder_path = self.targets.get_map_folder_path()
        event_config = self.targets.get_event_config()
        if not map_folder_path or not event_config:
            warn_event_config_missing(self.targets.parent)
            return False

        if save_event_config(map_folder_path, event_config):
            self.targets.refresh_event_dialog()
            show_event_config_saved(self.targets.parent)
            return True

        show_event_config_save_failed(self.targets.parent)
        return False

    def reset_portal_event_state(self, now_ms: int) -> bool:
        return self.reset_event_state(now_ms=now_ms)

    def reset_event_state(self, now_ms: int) -> bool:
        event_coordinator = self.targets.get_event_coordinator()
        event_config = self.targets.get_event_config()
        if not event_coordinator:
            warn_event_system_missing(self.targets.parent)
            return False

        if self.targets.portal_test_controller.active:
            self.set_portal_manual_test_active(False, reason="event state reset")

        self.targets.discard_async_event_results("event state reset")
        event_types = _configured_event_types(event_coordinator, event_config)
        removed_total = 0
        for event_type in event_types:
            removed_total += int(event_coordinator.reset_event_type(event_type, now_ms=now_ms) or 0)
        self.reset_event_move_runtime()
        self.targets.clear_event_overlay()
        self.targets.render_event_overlay()
        self.targets.refresh_event_dialog()
        event_log("all event state reset", removed=removed_total, event_types=",".join(event_types))
        show_event_state_reset(self.targets.status_label, removed_total)
        return True

    def run_portal_manual_test(self) -> bool:
        if self.targets.portal_test_controller.active:
            self.set_portal_manual_test_active(False, reason="button stop")
            return False

        if not self.targets.get_event_coordinator() or not self.targets.get_nav_core():
            self.targets.portal_test_controller.reset_button()
            warn_event_system_missing(self.targets.parent)
            return False

        nav_config = self.targets.get_nav_config()
        if not nav_config or not nav_config.game_screen_center:
            self.targets.portal_test_controller.reset_button()
            warn_portal_manual_test_missing_screen_center(self.targets.parent)
            return False

        if not self.targets.nav_timer.isActive():
            self.targets.start_button.setChecked(True)
            self.targets.toggle_navigation()
            if not self.targets.nav_timer.isActive():
                self.targets.portal_test_controller.reset_button()
                return False

        self.set_portal_manual_test_active(True, reason="button start")
        return True

    def set_portal_manual_test_active(self, active: bool, reason: str = "") -> None:
        if active:
            start_event_log_session("portal_manual_test")
            self.targets.navigation_task_controller.load_route(self._main_route())
            self.targets.navigation_task_controller.start()
            self.targets.portal_test_controller.start()
            self.targets.set_game_input_window_mode(True)
            self.targets.motion_controller.set_control_enabled(True)
            event_log("portal manual event test started", reason=reason)
            show_portal_manual_test_started(self.targets.status_label)
            return

        self.targets.portal_test_controller.stop()
        self.reset_event_move_runtime()
        if not self.targets.get_auto_navigation_enabled():
            self.targets.set_game_input_window_mode(False)
        event_log("portal manual event test stopped", reason=reason)
        show_portal_manual_test_stopped(self.targets.status_label)

    def reset_event_move_runtime(self) -> None:
        self.targets.navigation_task_controller.movement.reset()
        self.targets.navigation_task_controller.event_approach.reset()
        active_task_id = getattr(self.targets.navigation_task_controller, "active_task_id", None)
        if active_task_id and str(active_task_id).startswith("event:"):
            self.targets.navigation_task_controller.active_task_id = None

    def _main_route(self) -> dict:
        return (self.targets.get_route_data() or {}).get("routes", {}).get("main", {})


def _configured_event_types(event_coordinator, event_config) -> list[str]:
    values = set()
    raw_events = getattr(event_config, "events", None)
    if isinstance(raw_events, dict):
        values.update(str(key) for key in raw_events.keys())
    registry = getattr(event_coordinator, "registry", None)
    if registry is not None:
        try:
            values.update(str(definition.event_type) for definition in registry.definitions())
        except Exception:
            pass
    return sorted(value for value in values if value)
