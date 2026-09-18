from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from ..presentation import (
    apply_map_loaded_ui,
    show_map_load_failed,
    warn_map_config_missing,
)
from .session import NavigationMapLoadSession, prepare_navigation_map_load_session


@dataclass(frozen=True)
class NavigationMapLoadLifecycleTargets:
    parent: object
    source_file: str
    missing_label: str
    params_dialog: object
    start_button: object
    hint_button: object
    route_panel: object
    status_label: object
    compute_scale: Callable[[], tuple[float, float]]
    set_map_session: Callable[[NavigationMapLoadSession], None]
    apply_config_to_runtime: Callable[[], object]
    load_route_data: Callable[[], object]
    initialize_event_system: Callable[[], None]
    render_map: Callable[[], None]
    show_last_exit_position: Callable[[], None]
    render_route_overlay: Callable[[], None]


class NavigationMapLoadLifecycle:
    """Own the ordered GUI side effects for loading a navigation map."""

    def __init__(self, targets: NavigationMapLoadLifecycleTargets) -> None:
        self.targets = targets

    def load_selected_map(self, map_name: str | None) -> bool:
        if not map_name or map_name == self.targets.missing_label:
            return False

        try:
            session = prepare_navigation_map_load_session(
                source_file=self.targets.source_file,
                map_name=map_name,
                scale=self.targets.compute_scale(),
            )
            self.apply_loaded_session(session)
            return True
        except Exception as error:
            show_map_load_failed(self.targets.parent, error)
            return False

    def apply_loaded_session(self, session: NavigationMapLoadSession) -> None:
        self.targets.set_map_session(session)

        if not session.config_exists:
            warn_map_config_missing(self.targets.parent)

        self.targets.apply_config_to_runtime()
        self._announce_capture_center(session)
        self.targets.params_dialog.set_config_to_ui(session.nav_config)
        self.targets.load_route_data()
        self.targets.initialize_event_system()
        self.targets.render_map()
        self.targets.show_last_exit_position()
        self.targets.render_route_overlay()
        apply_map_loaded_ui(
            start_button=self.targets.start_button,
            hint_button=self.targets.hint_button,
            route_panel=self.targets.route_panel,
            status_label=self.targets.status_label,
            map_name=session.map_name,
        )

    @staticmethod
    def _announce_capture_center(session: NavigationMapLoadSession) -> None:
        if session.capture_center_physical:
            print(
                f"地图 '{session.map_name}' 加载完成，物理坐标："
                f"{session.capture_center_physical}"
            )
