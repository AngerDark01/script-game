"""Config and map folder storage helpers for mapping mode."""

from __future__ import annotations

import json
from pathlib import Path

from ....composition.paths import (
    map_data_dir_from_file,
    project_root_from_file,
    root_config_path_from_file,
)


def map_data_dir(file_path: str | Path) -> Path:
    return map_data_dir_from_file(file_path)


def map_folder_for_name(file_path: str | Path, map_name: str) -> Path:
    return map_data_dir(file_path) / map_name


def ensure_map_folder(file_path: str | Path, map_name: str) -> Path:
    folder = map_folder_for_name(file_path, map_name)
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def root_config_path(file_path: str | Path) -> Path:
    return root_config_path_from_file(file_path)


def build_mapping_config(app_context, fps: int, *, include_draw_scale: bool = False) -> dict:
    config = {
        "monitor_logical_center": app_context.monitor_logical_center,
        "monitor_size": app_context.monitor_size,
        "monitor_region": app_context.monitor_region,
        "fps": fps,
        "recognizer_params": app_context.recognizer.get_params(),
        "stitcher_params": app_context.stitcher.get_params(),
    }
    if include_draw_scale:
        config = {"draw_scale": app_context.stitcher.draw_scale, **config}
    return config


def save_json_config(path: str | Path, config: dict) -> None:
    with Path(path).open("w", encoding="utf-8") as handle:
        json.dump(config, handle, indent=4)


def load_json_config(path: str | Path) -> dict:
    with Path(path).open("r", encoding="utf-8") as handle:
        return json.load(handle)


def save_root_config(file_path: str | Path, config: dict) -> Path:
    path = root_config_path(file_path)
    save_json_config(path, config)
    return path


def load_root_config(file_path: str | Path) -> dict | None:
    path = root_config_path(file_path)
    if not path.exists():
        return None
    return load_json_config(path)


def save_map_config(map_folder: str | Path, config: dict) -> Path:
    path = Path(map_folder) / "config.json"
    save_json_config(path, config)
    return path
