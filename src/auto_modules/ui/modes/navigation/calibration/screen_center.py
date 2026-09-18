from __future__ import annotations

from PySide6.QtWidgets import QApplication

from ....selection.center_selector import CenterPointSelector


def screen_scale(screen=None) -> tuple[float, float]:
    screen = screen or QApplication.primaryScreen()
    if screen is None:
        return 1.0, 1.0
    dpr = screen.devicePixelRatio()
    if dpr > 0:
        return dpr, dpr
    return 1.0, 1.0


def physical_point_from_logical(
    x: int | float,
    y: int | float,
    scale: tuple[float, float],
) -> tuple[int, int]:
    sx, sy = scale
    return int(x * sx), int(y * sy)


class ScreenCenterCalibrationController:
    def __init__(self, *, selector_factory=CenterPointSelector, scale_provider=screen_scale):
        self._selector_factory = selector_factory
        self._scale_provider = scale_provider
        self.selector = None

    def start(self, on_point_selected) -> bool:
        if self.selector is not None and self.selector.isVisible():
            return False
        self.selector = self._selector_factory()
        self.selector.point_selected.connect(on_point_selected)
        self.selector.showFullScreen()
        return True

    def logical_to_physical(self, x: int | float, y: int | float) -> tuple[int, int]:
        return physical_point_from_logical(x, y, self._scale_provider())

    def close(self) -> None:
        if self.selector is not None:
            self.selector.close()
