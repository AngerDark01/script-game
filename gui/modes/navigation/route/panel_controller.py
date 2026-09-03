from __future__ import annotations

from dataclasses import dataclass

from .editor import MapClickMode, RouteEditor


@dataclass(frozen=True)
class RouteCommandResult:
    route_data: dict | None = None
    status_text: str | None = None
    saved: bool | None = None


class RoutePanelController:
    def __init__(
        self,
        route_editor: RouteEditor,
        *,
        set_exit_button,
        add_required_button,
        undo_required_button,
        add_guide_button,
        undo_guide_button,
        clear_route_button,
        save_route_button,
        auto_nav_button,
        status_label,
    ) -> None:
        self.route_editor = route_editor
        self.set_exit_button = set_exit_button
        self.add_required_button = add_required_button
        self.undo_required_button = undo_required_button
        self.add_guide_button = add_guide_button
        self.undo_guide_button = undo_guide_button
        self.clear_route_button = clear_route_button
        self.save_route_button = save_route_button
        self.auto_nav_button = auto_nav_button
        self.status_label = status_label

    def set_click_mode(self, mode: str | MapClickMode) -> MapClickMode:
        click_mode = self.route_editor.set_click_mode(mode)
        if click_mode != MapClickMode.SET_EXIT:
            self.set_exit_button.setChecked(False)
        if click_mode != MapClickMode.ADD_REQUIRED_POINT:
            self.add_required_button.setChecked(False)
        if click_mode != MapClickMode.ADD_GUIDE_POINT:
            self.add_guide_button.setChecked(False)
        return click_mode

    def toggle_exit_mode(self, map_folder_path: str | None) -> None:
        if not map_folder_path:
            self.set_exit_button.setChecked(False)
            return
        mode = MapClickMode.SET_EXIT if self.set_exit_button.isChecked() else MapClickMode.NONE
        self.set_click_mode(mode)
        if mode == MapClickMode.SET_EXIT:
            self.status_label.setText("请在地图上点击出口位置")

    def toggle_guide_mode(self, map_folder_path: str | None) -> None:
        if not map_folder_path:
            self.add_guide_button.setChecked(False)
            return
        mode = MapClickMode.ADD_GUIDE_POINT if self.add_guide_button.isChecked() else MapClickMode.NONE
        self.set_click_mode(mode)
        if mode == MapClickMode.ADD_GUIDE_POINT:
            self.status_label.setText("请在地图上点击A*辅助点；顺序仅用于撤销")

    def toggle_required_mode(self, map_folder_path: str | None) -> None:
        if not map_folder_path:
            self.add_required_button.setChecked(False)
            return
        mode = MapClickMode.ADD_REQUIRED_POINT if self.add_required_button.isChecked() else MapClickMode.NONE
        self.set_click_mode(mode)
        if mode == MapClickMode.ADD_REQUIRED_POINT:
            self.status_label.setText("请在地图上依次点击必经点")

    def set_buttons_enabled(self, enabled: bool) -> None:
        self.set_exit_button.setEnabled(enabled)
        self.add_required_button.setEnabled(enabled)
        self.undo_required_button.setEnabled(enabled)
        self.add_guide_button.setEnabled(enabled)
        self.undo_guide_button.setEnabled(enabled)
        self.clear_route_button.setEnabled(enabled)
        self.save_route_button.setEnabled(enabled)
        self.auto_nav_button.setEnabled(enabled)

    def save_route(self, map_folder_path: str | None) -> RouteCommandResult:
        if not map_folder_path:
            return RouteCommandResult(saved=None)
        saved = self.route_editor.save_route(map_folder_path)
        if not saved:
            return RouteCommandResult(saved=False)
        route_data = self.route_editor.load_route_data(map_folder_path, force_reload=True)
        return RouteCommandResult(route_data=route_data, status_text="路线已保存", saved=True)

    def undo_guide_point(self, map_folder_path: str | None) -> RouteCommandResult:
        if not map_folder_path:
            return RouteCommandResult()
        return RouteCommandResult(
            route_data=self.route_editor.undo_guide_point(map_folder_path),
            status_text="已撤销最后一个途经点",
        )

    def undo_required_point(self, map_folder_path: str | None) -> RouteCommandResult:
        if not map_folder_path:
            return RouteCommandResult()
        return RouteCommandResult(
            route_data=self.route_editor.undo_required_point(map_folder_path),
            status_text="已撤销最后一个必经点",
        )

    def clear_route(self, map_folder_path: str | None) -> RouteCommandResult:
        if not map_folder_path:
            return RouteCommandResult()
        return RouteCommandResult(
            route_data=self.route_editor.clear_route(map_folder_path),
            status_text="路线已清空",
        )
