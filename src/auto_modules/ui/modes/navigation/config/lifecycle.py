from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from ..map import (
    apply_motion_controller_config,
    apply_navigation_config_to_core,
    configure_navigation_task_controller,
    save_default_nav_config,
    save_nav_config,
)
from ..presentation.config_save_state import (
    mark_nav_params_dirty,
    show_default_nav_config_save_failed,
    show_default_nav_config_saved,
    show_nav_config_save_failed,
    show_nav_config_saved,
    warn_default_nav_config_missing,
    warn_nav_config_missing_map,
)


@dataclass(frozen=True)
class NavigationConfigLifecycleTargets:
    parent: object
    source_file: str
    nav_status_label: object
    path_finder: object
    motion_controller: object
    navigation_task_controller: object
    get_nav_config: Callable[[], object]
    set_nav_config: Callable[[object], None]
    get_nav_core: Callable[[], object]
    get_map_folder_path: Callable[[], str | None]
    reset_capture_center: Callable[[], None]
    update_overlay_display: Callable[[], None]
    refresh_game_view_rect_from_known_position: Callable[[], None]


class NavigationConfigLifecycle:
    """Own navigation config mutation, apply, save, and UI feedback order."""

    def __init__(self, targets: NavigationConfigLifecycleTargets) -> None:
        self.targets = targets

    def apply_to_runtime(self) -> bool:
        nav_core = self.targets.get_nav_core()
        nav_config = self.targets.get_nav_config()
        if not nav_core or not nav_config:
            return False

        self.targets.reset_capture_center()
        return apply_navigation_config_to_core(
            nav_config,
            nav_core=nav_core,
            path_finder=self.targets.path_finder,
            motion_controller=self.targets.motion_controller,
            navigation_task_controller=self.targets.navigation_task_controller,
        )

    def configure_task_controller(self) -> None:
        configure_navigation_task_controller(
            self.targets.get_nav_config(),
            nav_core=self.targets.get_nav_core(),
            navigation_task_controller=self.targets.navigation_task_controller,
        )

    def handle_parameter_changed(self, new_config) -> bool:
        if not self.targets.get_nav_core():
            return False

        self.targets.set_nav_config(new_config)
        self.targets.reset_capture_center()
        self.targets.update_overlay_display()
        apply_motion_controller_config(
            self.targets.get_nav_config(),
            self.targets.motion_controller,
        )
        self.configure_task_controller()
        self.targets.refresh_game_view_rect_from_known_position()
        mark_nav_params_dirty(self.targets.nav_status_label)
        return True

    def save_current_map_config(self) -> bool:
        map_folder_path = self.targets.get_map_folder_path()
        if not map_folder_path:
            warn_nav_config_missing_map(self.targets.parent)
            return False

        try:
            save_nav_config(map_folder_path, self.targets.get_nav_config())
            self.apply_to_runtime()
            self.targets.update_overlay_display()
            self.targets.refresh_game_view_rect_from_known_position()
            show_nav_config_saved(
                self.targets.parent,
                self.targets.nav_status_label,
            )
            return True
        except Exception as error:
            show_nav_config_save_failed(
                self.targets.parent,
                self.targets.nav_status_label,
                error,
            )
            return False

    def save_default_config(self) -> bool:
        nav_config = self.targets.get_nav_config()
        if not nav_config:
            warn_default_nav_config_missing(self.targets.parent)
            return False

        try:
            path = save_default_nav_config(self.targets.source_file, nav_config)
            show_default_nav_config_saved(
                self.targets.parent,
                self.targets.nav_status_label,
                path,
            )
            return True
        except Exception as error:
            show_default_nav_config_save_failed(
                self.targets.parent,
                self.targets.nav_status_label,
                error,
            )
            return False
