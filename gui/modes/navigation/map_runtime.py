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
        default_path = default_nav_config_path_from_map_folder(map_folder_path)
        if default_path.exists():
            with default_path.open("r", encoding="utf-8") as handle:
                return NavConfig.from_dict(json.load(handle)), False
        return NavConfig(), False
    with config_path.open("r", encoding="utf-8") as handle:
        return NavConfig.from_dict(json.load(handle)), True


def save_nav_config(map_folder_path: str, nav_config: NavConfig) -> None:
    config_path = Path(map_folder_path) / "config.json"
    existing: dict = {}
    if config_path.exists():
        try:
            with config_path.open("r", encoding="utf-8") as handle:
                existing = json.load(handle)
        except (OSError, json.JSONDecodeError):
            existing = {}
    updated = dict(existing)
    nav_data = nav_config.to_dict()
    existing_recognizer = dict(existing.get("recognizer_params", {}) or {})
    existing_recognizer.update(nav_data.pop("recognizer_params", {}) or {})
    updated.update(nav_data)
    updated["recognizer_params"] = existing_recognizer
    with config_path.open("w", encoding="utf-8") as handle:
        json.dump(updated, handle, indent=4, ensure_ascii=False)


def default_nav_config_path_from_file(file_path: str | Path) -> Path:
    return project_root_from_file(file_path) / "config.json"


def default_nav_config_path_from_map_folder(map_folder_path: str | Path) -> Path:
    return Path(map_folder_path).resolve().parents[1] / "config.json"


def save_default_nav_config(file_path: str | Path, nav_config: NavConfig) -> Path:
    """Merge navigation defaults into the project root config without dropping mapping-only fields."""
    config_path = default_nav_config_path_from_file(file_path)
    existing: dict = {}
    if config_path.exists():
        with config_path.open("r", encoding="utf-8") as handle:
            existing = json.load(handle)

    updated = dict(existing)
    nav_data = nav_config.to_dict()
    existing_recognizer = dict(existing.get("recognizer_params", {}) or {})
    existing_recognizer.update(nav_data.pop("recognizer_params", {}) or {})
    updated.update(nav_data)
    updated["recognizer_params"] = existing_recognizer

    with config_path.open("w", encoding="utf-8") as handle:
        json.dump(updated, handle, indent=4, ensure_ascii=False)
    return config_path


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
