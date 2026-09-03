from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QGraphicsView

from ..presentation import (
    create_initial_hint_marker,
    set_target_marker,
    show_hint_mode_status,
    show_initial_hint_set,
    show_move_target_set,
    show_route_command_status,
    warn_move_target_requires_localization,
)


@dataclass(frozen=True)
class NavigationMapClickLifecycleTargets:
    parent: object
    view: object
    scene: object
    status_label: object
    hint_button: object
    motion_controller: object
    route_editor: object
    get_nav_core: Callable[[], object]
    get_map_folder_path: Callable[[], str | None]
    set_route_data: Callable[[object], None]
    get_hint_item: Callable[[], object]
    set_hint_item: Callable[[object], None]
    get_target_item: Callable[[], object]
    render_route_overlay: Callable[[], None]
    set_map_click_mode: Callable[[str], None]
    update_monitor_rect: Callable[[tuple[float, float]], None]
    update_game_view_rect: Callable[[tuple[float, float]], None]


class NavigationMapClickLifecycle:
    """Own map click interpretation: hint placement, route editing, and manual move."""

    def __init__(self, targets: NavigationMapClickLifecycleTargets) -> None:
        self.targets = targets

    def handle_map_click(self, scene_pos) -> bool:
        nav_core = self.targets.get_nav_core()
        if not nav_core:
            return False

        global_point = self._scene_to_global_point(scene_pos, nav_core)
        if self.targets.hint_button.isChecked():
            self.set_initial_hint(scene_pos)
            return True

        route_result = self.targets.route_editor.handle_click(
            self.targets.get_map_folder_path(),
            global_point,
        )
        if route_result.handled:
            self.targets.set_route_data(route_result.route_data)
            if route_result.next_mode is not None:
                self.targets.set_map_click_mode(route_result.next_mode)
            self.targets.render_route_overlay()
            show_route_command_status(
                self.targets.status_label,
                route_result.status_text,
            )
            return True

        if not nav_core.is_localized or not nav_core.current_pos:
            warn_move_target_requires_localization(self.targets.parent)
            return False

        target_global_pos = (float(global_point[0]), float(global_point[1]))
        self.targets.motion_controller.move_to_map_target(
            nav_core.current_pos,
            target_global_pos,
        )
        set_target_marker(self.targets.get_target_item(), scene_pos)
        show_move_target_set(self.targets.status_label, scene_pos)
        return True

    def set_initial_hint(self, scene_pos) -> None:
        nav_core = self.targets.get_nav_core()
        if not nav_core:
            return

        global_x, global_y = self._scene_to_global_position(scene_pos, nav_core)
        nav_core.set_initial_hint((global_x, global_y))
        hint_item = create_initial_hint_marker(
            self.targets.scene,
            self.targets.get_hint_item(),
            scene_pos,
        )
        self.targets.set_hint_item(hint_item)
        self.targets.update_monitor_rect((global_x, global_y))
        self.targets.update_game_view_rect((global_x, global_y))
        self._print_hint_debug(scene_pos, nav_core, global_x, global_y)
        show_initial_hint_set(self.targets.status_label, global_x, global_y)
        self.targets.hint_button.setChecked(False)
        self.toggle_hint_mode()

    def toggle_hint_mode(self) -> None:
        is_hint_mode = self.targets.hint_button.isChecked()
        self.targets.view.setDragMode(
            QGraphicsView.NoDrag if is_hint_mode else QGraphicsView.ScrollHandDrag
        )
        self.targets.view.setCursor(Qt.CrossCursor if is_hint_mode else Qt.ArrowCursor)
        show_hint_mode_status(self.targets.status_label, is_hint_mode)

    @staticmethod
    def _scene_to_global_point(scene_pos, nav_core) -> tuple[int, int]:
        global_x, global_y = NavigationMapClickLifecycle._scene_to_global_position(
            scene_pos,
            nav_core,
        )
        return int(global_x), int(global_y)

    @staticmethod
    def _scene_to_global_position(scene_pos, nav_core) -> tuple[float, float]:
        offset_x, offset_y = nav_core.crop_offset
        return scene_pos.x() + offset_x, scene_pos.y() + offset_y

    @staticmethod
    def _print_hint_debug(scene_pos, nav_core, global_x: float, global_y: float) -> None:
        offset_x, offset_y = nav_core.crop_offset
        print("=== 设置初始位置提示 (用户点击) ===")
        print(f"  - 点击的显示坐标: ({scene_pos.x():.2f}, {scene_pos.y():.2f})")
        print(f"  - 地图裁剪偏移量: ({offset_x:.2f}, {offset_y:.2f})")
        print(f"  - 转换后的全局坐标: ({global_x:.2f}, {global_y:.2f})")
