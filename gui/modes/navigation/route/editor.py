from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class MapClickMode(StrEnum):
    NONE = "NONE"
    SET_EXIT = "SET_EXIT"
    ADD_REQUIRED_POINT = "ADD_REQUIRED_POINT"
    ADD_GUIDE_POINT = "ADD_GUIDE_POINT"


@dataclass(frozen=True)
class RouteEditResult:
    handled: bool
    route_data: dict | None = None
    next_mode: MapClickMode | None = None
    status_text: str | None = None


class RouteEditor:
    """Owns route click-mode state and route.json edit commands."""

    def __init__(self, route_manager) -> None:
        self.route_manager = route_manager
        self.click_mode = MapClickMode.NONE

    def set_click_mode(self, mode: str | MapClickMode) -> MapClickMode:
        self.click_mode = _coerce_mode(mode)
        return self.click_mode

    def load_route_data(self, map_folder_path: str | None, *, force_reload: bool = True) -> dict | None:
        if not map_folder_path:
            return None
        return self.route_manager.load_route(map_folder_path, force_reload=force_reload)

    def save_route(self, map_folder_path: str | None) -> bool:
        if not map_folder_path:
            return False
        return self.route_manager.save_route(map_folder_path)

    def undo_guide_point(self, map_folder_path: str | None) -> dict | None:
        if not map_folder_path:
            return None
        self.route_manager.undo_guide_point(map_folder_path)
        return self.route_manager.load_route(map_folder_path)

    def undo_required_point(self, map_folder_path: str | None) -> dict | None:
        if not map_folder_path:
            return None
        self.route_manager.undo_required_point(map_folder_path)
        return self.route_manager.load_route(map_folder_path)

    def clear_route(self, map_folder_path: str | None) -> dict | None:
        if not map_folder_path:
            return None
        self.route_manager.clear_route(map_folder_path)
        return self.route_manager.load_route(map_folder_path)

    def handle_click(self, map_folder_path: str | None, global_point) -> RouteEditResult:
        if not map_folder_path or self.click_mode == MapClickMode.NONE:
            return RouteEditResult(False)

        x, y = int(global_point[0]), int(global_point[1])
        if self.click_mode == MapClickMode.SET_EXIT:
            self.route_manager.set_exit_region(map_folder_path, (x, y), radius=28)
            route_data = self.route_manager.load_route(map_folder_path)
            self.click_mode = MapClickMode.NONE
            return RouteEditResult(
                True,
                route_data=route_data,
                next_mode=MapClickMode.NONE,
                status_text=f"出口已设置: ({x}, {y})",
            )

        if self.click_mode == MapClickMode.ADD_REQUIRED_POINT:
            self.route_manager.add_required_point(map_folder_path, (x, y))
            route_data = self.route_manager.load_route(map_folder_path)
            return RouteEditResult(
                True,
                route_data=route_data,
                status_text=f"已添加必经点: ({x}, {y})",
            )

        if self.click_mode == MapClickMode.ADD_GUIDE_POINT:
            self.route_manager.add_guide_point(map_folder_path, (x, y))
            route_data = self.route_manager.load_route(map_folder_path)
            return RouteEditResult(
                True,
                route_data=route_data,
                status_text=f"已添加途经点: ({x}, {y})",
            )

        return RouteEditResult(False)


def _coerce_mode(mode: str | MapClickMode) -> MapClickMode:
    if isinstance(mode, MapClickMode):
        return mode
    try:
        return MapClickMode(str(mode))
    except ValueError:
        return MapClickMode.NONE
