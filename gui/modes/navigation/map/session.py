from __future__ import annotations

from dataclasses import dataclass

from core.localization import NavigationCore

from ....navigation_params import NavConfig
from .config_store import load_nav_config


@dataclass(frozen=True)
class NavigationMapSettings:
    nav_config: NavConfig
    config_exists: bool


@dataclass(frozen=True)
class NavigationMapLoadSession:
    map_name: str
    map_folder_path: str
    nav_config: NavConfig
    config_exists: bool
    nav_core: NavigationCore
    capture_center_physical: tuple[int, int] | None
    physical_center: tuple[int, int]


def load_navigation_map_settings(map_folder_path: str) -> NavigationMapSettings:
    nav_config, config_exists = load_nav_config(map_folder_path)
    return NavigationMapSettings(nav_config=nav_config, config_exists=config_exists)


def create_navigation_core(map_folder_path: str) -> NavigationCore:
    return NavigationCore(map_folder_path)


def prepare_navigation_map_load_session(
    *,
    source_file: str,
    map_name: str,
    scale: tuple[float, float],
) -> NavigationMapLoadSession:
    from .capture_geometry import initial_capture_center_for_config
    from .config_store import resolve_map_folder

    map_folder_path = resolve_map_folder(source_file, map_name)
    settings = load_navigation_map_settings(map_folder_path)
    nav_core = create_navigation_core(map_folder_path)
    capture_center_physical, physical_center = initial_capture_center_for_config(
        settings.nav_config,
        scale,
    )
    return NavigationMapLoadSession(
        map_name=map_name,
        map_folder_path=map_folder_path,
        nav_config=settings.nav_config,
        config_exists=settings.config_exists,
        nav_core=nav_core,
        capture_center_physical=capture_center_physical,
        physical_center=physical_center,
    )
