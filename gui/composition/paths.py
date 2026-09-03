from __future__ import annotations

from pathlib import Path


def project_root_from_file(file_path: str | Path) -> Path:
    """Resolve the project root from a source file or directory inside the app."""
    path = Path(file_path).resolve()
    start = path if path.is_dir() else path.parent
    for candidate in (start, *start.parents):
        if (candidate / "main.py").exists() and (candidate / "gui").exists():
            return candidate
    raise FileNotFoundError(f"Could not resolve project root from {file_path!s}")


def project_root_from_map_folder(map_folder_path: str | Path) -> Path:
    """Resolve the project root from a map_data/<map_name> folder."""
    path = Path(map_folder_path).resolve()
    for candidate in (path, *path.parents):
        if candidate.name == "map_data":
            return candidate.parent
    return project_root_from_file(path)


def map_data_dir_from_file(file_path: str | Path) -> Path:
    return project_root_from_file(file_path) / "map_data"


def root_config_path_from_file(file_path: str | Path) -> Path:
    return project_root_from_file(file_path) / "config.json"


def root_config_path_from_map_folder(map_folder_path: str | Path) -> Path:
    return project_root_from_map_folder(map_folder_path) / "config.json"


def advanced_settings_dir_from_file(file_path: str | Path) -> Path:
    return project_root_from_file(file_path) / "configs" / "advanced_settings"
