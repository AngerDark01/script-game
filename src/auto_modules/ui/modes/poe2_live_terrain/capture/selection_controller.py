"""PoE2-local copy of the proven mapping capture interaction."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from PySide6.QtCore import Qt

from auto_modules.core.spatial.monitor_binding import (
    CaptureRect,
    MonitorBinding,
    resize_binding_around_marker,
)
from auto_modules.ui.selection.center_selector import CenterPointSelector
from auto_modules.ui.selection.region_overlay import TransparentOverlay


@dataclass(frozen=True)
class Poe2CaptureSelectionResult:
    mode: str
    binding: MonitorBinding
    capture_size: int
    label_text: str


class Poe2CaptureSelectionController:
    """Own PoE2 overlay lifecycle without writing mapping-mode state."""

    def __init__(
        self,
        *,
        compute_scale: Callable[[], tuple[float, float]],
        overlay_factory: Callable[[], TransparentOverlay] = TransparentOverlay,
        center_selector_factory: Callable[[], CenterPointSelector] = CenterPointSelector,
    ) -> None:
        self.compute_scale = compute_scale
        self.overlay_factory = overlay_factory
        self.center_selector_factory = center_selector_factory
        self.overlay_active = False
        self.center_selector_active = False
        self.overlay: TransparentOverlay | None = None
        self.center_selector: CenterPointSelector | None = None

    def start_region_selection(self, on_selected: Callable[[Poe2CaptureSelectionResult], None]) -> bool:
        if self.overlay_active:
            return False
        overlay = self.overlay_factory()
        overlay.setAttribute(Qt.WA_DeleteOnClose, True)
        overlay.region_selected.connect(
            lambda x, y, width, height: self._handle_region_selected(
                x, y, width, height, on_selected
            )
        )
        overlay.destroyed.connect(self._clear_region_overlay)
        self.overlay = overlay
        self.overlay_active = True
        overlay.showFullScreen()
        return True

    def start_center_selection(
        self,
        capture_size: int,
        on_selected: Callable[[Poe2CaptureSelectionResult], None],
    ) -> bool:
        if self.center_selector_active:
            return False
        selector = self.center_selector_factory()
        selector.setAttribute(Qt.WA_DeleteOnClose, True)
        selector.point_selected.connect(
            lambda x, y: self._handle_center_selected(x, y, capture_size, on_selected)
        )
        selector.selection_cancelled.connect(self._clear_center_selector)
        selector.destroyed.connect(self._clear_center_selector)
        self.center_selector = selector
        self.center_selector_active = True
        selector.showFullScreen()
        return True

    def apply_region_selection(
        self, x: int, y: int, width: int, height: int
    ) -> Poe2CaptureSelectionResult:
        sx, sy = self.compute_scale()
        rect = CaptureRect(int(x * sx), int(y * sy), int(width * sx), int(height * sy))
        binding = MonitorBinding(rect=rect, dpi_scale_x=sx, dpi_scale_y=sy)
        return Poe2CaptureSelectionResult(
            mode="region",
            binding=binding,
            capture_size=min(rect.width, rect.height),
            label_text=f"物理: ({rect.left}, {rect.top}) {rect.width}x{rect.height}",
        )

    def apply_center_selection(self, x: int, y: int, capture_size: int) -> Poe2CaptureSelectionResult:
        sx, sy = self.compute_scale()
        size = max(1, int(capture_size))
        physical_center = (int(x * sx), int(y * sy))
        # The capture backend and mapping mode both define size in physical pixels.
        physical_size = size
        left = physical_center[0] - physical_size // 2
        top = physical_center[1] - physical_size // 2
        binding = MonitorBinding(
            rect=CaptureRect(left, top, physical_size, physical_size),
            dpi_scale_x=sx,
            dpi_scale_y=sy,
            player_marker_position=(physical_size // 2, physical_size // 2),
        )
        return Poe2CaptureSelectionResult(
            mode="center",
            binding=binding,
            capture_size=size,
            label_text=(
                f"中心: {physical_center}, 物理区域: "
                f"({left}, {top}) {physical_size}x{physical_size}"
            ),
        )

    @staticmethod
    def resize_center_binding(binding: MonitorBinding, capture_size: int) -> MonitorBinding:
        """Resize a center-mode binding without moving its physical anchor."""
        size = max(1, int(capture_size))
        return resize_binding_around_marker(binding, size, size)

    def _handle_region_selected(self, x, y, width, height, callback) -> None:
        self.overlay_active = False
        callback(self.apply_region_selection(x, y, width, height))

    def _handle_center_selected(self, x, y, capture_size, callback) -> None:
        self.center_selector_active = False
        callback(self.apply_center_selection(x, y, capture_size))

    def _clear_region_overlay(self, *_args) -> None:
        self.overlay_active = False
        self.overlay = None

    def _clear_center_selector(self, *_args) -> None:
        self.center_selector_active = False
        self.center_selector = None


__all__ = ["Poe2CaptureSelectionController", "Poe2CaptureSelectionResult"]
