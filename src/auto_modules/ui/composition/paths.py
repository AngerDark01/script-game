from __future__ import annotations

from pathlib import Path
from auto_modules.paths import data_root, repository_root


def project_root_from_file(file_path: str | Path) -> Path:
    """Return the source checkout or installed application root."""
    del file_path
    return repository_root()


def project_root_from_map_folder(map_folder_path: str | Path) -> Path:
    """Return the application root without inferring it from writable data."""
    del map_folder_path
    return repository_root()


def map_data_dir_from_file(file_path: str | Path) -> Path:
    del file_path
    return data_root() / "maps"


def root_config_path_from_file(file_path: str | Path) -> Path:
    del file_path
    return data_root() / "config.json"


def root_config_path_from_map_folder(map_folder_path: str | Path) -> Path:
    del map_folder_path
    return data_root() / "config.json"


def advanced_settings_dir_from_file(file_path: str | Path) -> Path:
    del file_path
    return data_root() / "settings" / "advanced"
