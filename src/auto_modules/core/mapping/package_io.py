from __future__ import annotations

import os

import numpy as np


def save_stitcher_map_package(stitcher, folder_path) -> None:
    """Persist the current MapStitcher map package."""
    if not os.path.exists(folder_path):
        os.makedirs(folder_path)

    np.savez_compressed(
        os.path.join(folder_path, "map_data.npz"),
        canvas=stitcher.canvas,
        weight_layer=stitcher.weight_layer,
        explored_map=stitcher.explored_map,
        wall_layer=stitcher.wall_layer,
        fog_layer=stitcher.fog_layer,
        current_pos=np.array([stitcher.current_x, stitcher.current_y]),
        canvas_size=stitcher.canvas_size,
        draw_scale=stitcher.draw_scale,
        wall_close_kernel_size=stitcher.wall_close_kernel_size,
    )


def load_stitcher_map_package(stitcher, folder_path) -> bool:
    """Load a saved map package into an existing MapStitcher instance."""
    data_path = os.path.join(folder_path, "map_data.npz")
    if not os.path.exists(data_path):
        print(f"错误: 找不到地图数据 {data_path}")
        return False

    try:
        data = np.load(data_path)

        saved_size = int(data["canvas_size"])
        if saved_size != stitcher.canvas_size:
            print(
                f"警告: 地图尺寸不匹配 (保存: {saved_size}, 当前: {stitcher.canvas_size})，可能导致加载失败"
            )

        stitcher.canvas = data["canvas"]
        stitcher.weight_layer = data["weight_layer"]
        stitcher.explored_map = data["explored_map"]

        if "wall_layer" in data:
            stitcher.wall_layer = data["wall_layer"]
        if "fog_layer" in data:
            stitcher.fog_layer = data["fog_layer"]

        if "current_pos" in data:
            pos = data["current_pos"]
            stitcher.current_x = float(pos[0])
            stitcher.current_y = float(pos[1])

        print(f"地图加载成功: {folder_path}")
        return True
    except Exception as exc:
        print(f"加载地图失败: {exc}")
        return False
