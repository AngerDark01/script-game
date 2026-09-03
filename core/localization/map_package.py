from __future__ import annotations

import numpy as np

from core.routing.obstacles import derive_navigation_wall_layer


def load_navigation_map_package(nav_core) -> None:
    """Load map_data.npz fields into a NavigationCore instance."""
    try:
        data = np.load(nav_core.map_data_path)
        nav_core.wall_layer = data["wall_layer"]
        nav_core.nav_wall_layer = (
            data["nav_wall_layer"]
            if "nav_wall_layer" in data
            else derive_navigation_wall_layer(
                nav_core.wall_layer,
                erode_iterations=nav_core.nav_wall_erode_iterations,
            )
        )
        nav_core.explored_map = data["explored_map"] if "explored_map" in data else None
        nav_core.fog_layer = data["fog_layer"] if "fog_layer" in data else np.zeros_like(nav_core.wall_layer)
        nav_core.canvas_size = int(data["canvas_size"]) if "canvas_size" in data else 10000

        if "draw_scale" in data:
            nav_core.draw_scale = float(data["draw_scale"])
            nav_core.map_draw_scale = nav_core.draw_scale
            nav_core._clear_frame_registration(0.0, "map_loaded")

        if "wall_close_kernel_size" in data:
            nav_core.wall_match_close_kernel_size = max(1, int(data["wall_close_kernel_size"]))
            nav_core.map_wall_match_close_kernel_size = nav_core.wall_match_close_kernel_size

        if "current_pos" in data:
            pos_data = data["current_pos"]
            nav_core.drawing_saved_pos = (float(pos_data[0]), float(pos_data[1]))
            nav_core.last_pos = nav_core.drawing_saved_pos
            print(
                "=== 加载上次退出位置 (绘图模式保存): "
                f"({nav_core.drawing_saved_pos[0]:.2f}, {nav_core.drawing_saved_pos[1]:.2f}) ==="
            )
        else:
            print("⚠️ npz 文件中没有 current_pos 数据")

        print(f"Map loaded. Size: {nav_core.canvas_size}x{nav_core.canvas_size}")
    except Exception as exc:
        raise RuntimeError(f"Failed to load map data: {str(exc)}")
