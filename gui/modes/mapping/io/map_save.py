"""Map package and per-map config save orchestration."""

from __future__ import annotations

from .config_store import ensure_map_folder, save_map_config


def save_mapping_map(file_path, map_name: str, *, stitcher, config_data: dict):
    """Save the current map package and its map-level config."""
    map_folder = ensure_map_folder(file_path, map_name)
    stitcher.save_map_package(str(map_folder))
    save_map_config(map_folder, config_data)
    return map_folder
