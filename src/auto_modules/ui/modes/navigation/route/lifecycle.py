from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from ..presentation import show_route_command_status, warn_route_save_failed


@dataclass(frozen=True)
class NavigationRouteLifecycleTargets:
    parent: object
    status_label: object
    route_editor: object
    route_panel: object
    navigation_task_controller: object
    get_map_folder_path: Callable[[], str | None]
    set_route_data: Callable[[dict | None], None]
    render_route_overlay: Callable[[], None]


class NavigationRouteLifecycle:
    """Own route command result synchronization for the navigation page."""

    def __init__(self, targets: NavigationRouteLifecycleTargets) -> None:
        self.targets = targets

    def load_route_data(self) -> dict | None:
        map_folder_path = self.targets.get_map_folder_path()
        if not map_folder_path:
            self._sync_route_data(None)
            return None

        route_data = self.targets.route_editor.load_route_data(
            map_folder_path,
            force_reload=True,
        )
        self._sync_route_data(route_data)
        return route_data

    def save_route(self) -> None:
        result = self.targets.route_panel.save_route(self.targets.get_map_folder_path())
        if result.saved is None:
            return
        if not result.saved:
            warn_route_save_failed(self.targets.parent)
            return
        self._apply_route_command_result(result)

    def undo_guide_point(self) -> None:
        result = self.targets.route_panel.undo_guide_point(
            self.targets.get_map_folder_path(),
        )
        self._apply_route_command_result(result)

    def undo_required_point(self) -> None:
        result = self.targets.route_panel.undo_required_point(
            self.targets.get_map_folder_path(),
        )
        self._apply_route_command_result(result)

    def clear_route(self) -> None:
        result = self.targets.route_panel.clear_route(self.targets.get_map_folder_path())
        self._apply_route_command_result(result)

    def _apply_route_command_result(self, result) -> bool:
        if result.route_data is None:
            return False
        self._sync_route_data(result.route_data)
        self.targets.render_route_overlay()
        if result.status_text:
            show_route_command_status(self.targets.status_label, result.status_text)
        return True

    def _sync_route_data(self, route_data: dict | None) -> None:
        self.targets.set_route_data(route_data)
        main_route = (route_data or {}).get("routes", {}).get("main", {})
        self.targets.navigation_task_controller.load_route(
            main_route if route_data else None,
        )
