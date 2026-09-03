from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from ..presentation import show_screen_center_calibrated


@dataclass(frozen=True)
class NavigationScreenCalibrationLifecycleTargets:
    parent: object
    controller: object
    params_dialog: object
    get_nav_config: Callable[[], object]
    set_center_selector: Callable[[object], None]
    update_overlay_display: Callable[[], None]
    save_nav_config: Callable[[], object]


class NavigationScreenCalibrationLifecycle:
    """Own screen-center calibration side effects for the navigation page."""

    def __init__(self, targets: NavigationScreenCalibrationLifecycleTargets) -> None:
        self.targets = targets

    def start_screen_center_calibration(self) -> bool:
        started = self.targets.controller.start(self.handle_screen_center_click)
        self.targets.set_center_selector(self.targets.controller.selector)
        return started

    def handle_screen_center_click(self, x: int | float, y: int | float) -> tuple[int, int] | None:
        nav_config = self.targets.get_nav_config()
        if not nav_config:
            self.targets.controller.close()
            return None

        screen_center = self.targets.controller.logical_to_physical(x, y)
        nav_config.game_screen_center = screen_center
        print(f"Screen center calibrated at physical coordinates: {screen_center}")

        self.targets.params_dialog.set_config_to_ui(nav_config)
        self.targets.update_overlay_display()
        self.targets.save_nav_config()
        show_screen_center_calibrated(self.targets.parent, screen_center)
        self.targets.controller.close()
        return screen_center
