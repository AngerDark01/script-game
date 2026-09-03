from __future__ import annotations

from ..presentation import (
    clear_event_overlay,
    clear_route_overlay,
    create_last_position_marker,
    create_map_scene_items,
    global_to_scene,
    render_event_overlay,
    render_route_overlay,
    update_game_view_rect_item,
    update_monitor_rect_item,
)


class NavigationMapDisplayLifecycle:
    """Own scene item and overlay state writes for the navigation page."""

    def __init__(self, owner) -> None:
        self.owner = owner

    def clear_route_overlay(self) -> None:
        owner = self.owner
        owner.route_overlay_items, owner.route_path_item = clear_route_overlay(
            owner.scene,
            owner.route_overlay_items,
        )

    def clear_event_overlay(self) -> None:
        owner = self.owner
        owner.event_overlay_items = clear_event_overlay(
            owner.scene,
            owner.event_overlay_items,
        )

    def global_to_scene(self, point):
        return global_to_scene(point, self.owner.nav_core)

    def render_event_overlay(self) -> None:
        owner = self.owner
        owner.event_overlay_items = render_event_overlay(
            owner.scene,
            owner.nav_core,
            owner.event_coordinator,
            owner.event_overlay_items,
        )

    def render_route_overlay(
        self,
        current_path=None,
        current_subgoal=None,
        current_required_index=None,
        current_guide_index=None,
        current_target_kind=None,
    ) -> None:
        owner = self.owner
        if not owner.scene or not owner.nav_core:
            return

        owner.route_overlay_items, owner.route_path_item = render_route_overlay(
            owner.scene,
            owner.nav_core,
            owner.route_data,
            owner.route_overlay_items,
            current_path=current_path,
            current_subgoal=current_subgoal,
            current_required_index=current_required_index,
            current_guide_index=current_guide_index,
            current_target_kind=current_target_kind,
        )
        self.render_event_overlay()

    def render_map(self) -> None:
        owner = self.owner
        items = create_map_scene_items(owner.scene, owner.view, owner.nav_core)
        owner.route_overlay_items = []
        owner.event_overlay_items = []
        owner.route_path_item = None
        owner.map_item = items["map_item"]
        owner.last_pos_item = None
        owner.hint_item = None
        owner.player_item = items["player_item"]
        owner.target_item = items["target_item"]
        owner.monitor_rect_item = items["monitor_rect_item"]
        owner.game_view_rect_item = items["game_view_rect_item"]

    def update_monitor_rect(self, player_pos, capture_rect=None, player_local_pos=None) -> None:
        owner = self.owner
        update_monitor_rect_item(
            owner.monitor_rect_item,
            player_pos=player_pos,
            capture_rect=capture_rect or owner._current_capture_rect,
            player_local_pos=player_local_pos or owner._current_player_local_pos,
            nav_core=owner.nav_core,
        )

    def update_game_view_rect(self, player_pos) -> None:
        owner = self.owner
        update_game_view_rect_item(
            owner.game_view_rect_item,
            player_pos=player_pos,
            nav_core=owner.nav_core,
            nav_config=owner.nav_config,
        )

    def refresh_game_view_rect_from_known_position(self) -> None:
        owner = self.owner
        if not owner.nav_core:
            return

        player_pos = (
            owner.nav_core.current_pos
            or owner.nav_core.last_good_pos
            or owner.nav_core.drawing_saved_pos
        )
        if player_pos:
            self.update_game_view_rect(player_pos)

    def show_last_exit_position(self) -> None:
        owner = self.owner
        if not owner.nav_core or not owner.nav_core.drawing_saved_pos:
            print("没有上次退出的位置信息")
            return

        last_pos_global = owner.nav_core.drawing_saved_pos
        print("=== 加载地图：显示上次退出位置 (绘图模式保存) ===")
        print(
            "  1. 上次退出位置 (绘图模式): "
            f"({last_pos_global[0]:.2f}, {last_pos_global[1]:.2f})"
        )

        owner.last_pos_item = create_last_position_marker(
            owner.scene,
            owner.last_pos_item,
            owner.nav_core,
            last_pos_global,
        )
