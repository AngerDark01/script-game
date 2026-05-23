from __future__ import annotations

import json
from pathlib import Path

from ...navigation_params import NavConfig


MISSING_MAP_DATA_LABEL = "未找到 map_data 文件夹"


def project_root_from_file(file_path: str | Path) -> Path:
    return Path(file_path).resolve().parents[2]


def map_data_dir(file_path: str | Path) -> Path:
    return project_root_from_file(file_path) / "map_data"


def list_map_names(file_path: str | Path) -> list[str]:
    root = map_data_dir(file_path)
    if not root.exists():
        return []
    return [path.name for path in root.iterdir() if path.is_dir()]


def resolve_map_folder(file_path: str | Path, map_name: str) -> str:
    return str(map_data_dir(file_path) / map_name)


def load_nav_config(map_folder_path: str) -> tuple[NavConfig, bool]:
    config_path = Path(map_folder_path) / "config.json"
    if not config_path.exists():
        return NavConfig(), False
    with config_path.open("r", encoding="utf-8") as handle:
        return NavConfig.from_dict(json.load(handle)), True


def save_nav_config(map_folder_path: str, nav_config: NavConfig) -> None:
    config_path = Path(map_folder_path) / "config.json"
    with config_path.open("w", encoding="utf-8") as handle:
        json.dump(nav_config.to_dict(), handle, indent=4, ensure_ascii=False)


def physical_center_from_logical(logical_center, scale: tuple[float, float]) -> tuple[int, int] | None:
    if not logical_center:
        return None
    sx, sy = scale
    logical_x, logical_y = logical_center
    return int(logical_x * sx), int(logical_y * sy)


def build_capture_geometry(nav_config: NavConfig | None, capture_center_physical):
    if not nav_config:
        return None, None, capture_center_physical

    size = nav_config.monitor_size
    region = nav_config.monitor_region

    if region:
        rect = {
            "left": int(region["left"]),
            "top": int(region["top"]),
            "width": int(region["width"]),
            "height": int(region["height"]),
        }
        return rect, None, capture_center_physical

    if not nav_config.monitor_logical_center or capture_center_physical is None:
        return None, None, capture_center_physical

    center_x, center_y = capture_center_physical
    half_size = size // 2
    rect = {
        "left": int(center_x - half_size),
        "top": int(center_y - half_size),
        "width": int(size),
        "height": int(size),
    }
    player_pos = (rect["width"] // 2, rect["height"] // 2)
    return rect, player_pos, capture_center_physical

