"""Capture region and center-point selection coordination for mapping mode."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal

from PySide6.QtCore import Qt

from ....selection.center_selector import CenterPointSelector
from ....selection.region_overlay import TransparentOverlay


@dataclass(frozen=True)
class CaptureSelectionResult:
    """Result of applying a mapping capture selection to AppContext."""

    mode: Literal["region", "center"]
    label_text: str
    monitor_region: dict[str, int] | None = None
    logical_center: tuple[int, int] | None = None
    physical_center: tuple[int, int] | None = None
    monitor_size: int | None = None


class MappingCaptureSelectionController:
    """Owns mapping capture selection overlays and AppContext write-back rules."""

    def __init__(
        self,
        app_context,
        *,
        compute_scale: Callable[[], tuple[float, float]],
        overlay_factory: Callable[[], TransparentOverlay] = TransparentOverlay,
        center_selector_factory: Callable[[], CenterPointSelector] = CenterPointSelector,
    ) -> None:
        self.app_context = app_context
        self.compute_scale = compute_scale
        self.overlay_factory = overlay_factory
        self.center_selector_factory = center_selector_factory

        self.overlay_active = False
        self.center_selector_active = False
        self.overlay: TransparentOverlay | None = None
        self.center_selector: CenterPointSelector | None = None
        self.monitor_center: tuple[int, int] | None = None

    def start_region_selection(self, on_selected: Callable[[CaptureSelectionResult], None]) -> bool:
        """Show the region overlay and call back with an applied selection result."""
        if self.overlay_active:
            return False

        overlay = self.overlay_factory()
        overlay.setAttribute(Qt.WA_DeleteOnClose, True)
        overlay.region_selected.connect(lambda x, y, width, height: self._handle_region_selected(
            x,
            y,
            width,
            height,
            on_selected,
        ))
        overlay.destroyed.connect(self._clear_region_overlay)

        self.overlay = overlay
        self.overlay_active = True
        overlay.showFullScreen()
        return True

    def start_center_selection(self, on_selected: Callable[[CaptureSelectionResult], None]) -> bool:
        """Show the center selector and call back with an applied selection result."""
        if self.center_selector_active:
            return False

        selector = self.center_selector_factory()
        selector.setAttribute(Qt.WA_DeleteOnClose, True)
        selector.point_selected.connect(lambda x, y: self._handle_center_selected(x, y, on_selected))
        selector.selection_cancelled.connect(self._clear_center_selector)
        selector.destroyed.connect(self._clear_center_selector)

        self.center_selector = selector
        self.center_selector_active = True
        selector.showFullScreen()
        return True

    def apply_region_selection(self, x: int, y: int, width: int, height: int) -> CaptureSelectionResult:
        """Store logical overlay rectangle as a physical monitor capture region."""
        sx, sy = self.compute_scale()
        px_left = int(x * sx)
        px_top = int(y * sy)
        px_width = int(width * sx)
        px_height = int(height * sy)

        monitor_region = {
            "left": px_left,
            "top": px_top,
            "width": px_width,
            "height": px_height,
        }
        self.app_context.monitor_region = monitor_region
        self.app_context.monitor_logical_center = None
        self.monitor_center = None

        return CaptureSelectionResult(
            mode="region",
            monitor_region=monitor_region,
            label_text=f"物理: ({px_left}, {px_top}) {px_width}x{px_height}",
        )

    def apply_center_selection(self, x: int, y: int, monitor_size: int) -> CaptureSelectionResult:
        """Store logical center selection and its physical center for square capture."""
        logical_center = (int(x), int(y))
        monitor_size = int(monitor_size)
        sx, sy = self.compute_scale()
        physical_center = (int(logical_center[0] * sx), int(logical_center[1] * sy))

        self.app_context.monitor_logical_center = logical_center
        self.app_context.monitor_size = monitor_size
        self.app_context.monitor_region = None
        self.monitor_center = physical_center

        return CaptureSelectionResult(
            mode="center",
            logical_center=logical_center,
            physical_center=physical_center,
            monitor_size=monitor_size,
            label_text=f"逻辑: ({logical_center[0]}, {logical_center[1]}), 物理: {physical_center}, 大小: {monitor_size}",
        )

    def update_capture_size(self, size: int) -> CaptureSelectionResult | None:
        """Update square capture size and refresh center selection if center mode is active."""
        self.app_context.monitor_size = int(size)
        logical_center = self.app_context.monitor_logical_center
        if not logical_center:
            return None
        return self.apply_center_selection(logical_center[0], logical_center[1], int(size))

    def restore_from_context(self) -> CaptureSelectionResult | None:
        """Build display state from saved AppContext capture selection fields."""
        if self.app_context.monitor_logical_center:
            logical_center = self.app_context.monitor_logical_center
            return self.apply_center_selection(
                logical_center[0],
                logical_center[1],
                getattr(self.app_context, "monitor_size", 320),
            )

        if self.app_context.monitor_region:
            region = self.app_context.monitor_region
            self.monitor_center = None
            return CaptureSelectionResult(
                mode="region",
                monitor_region=region,
                label_text=f"物理: ({region['left']}, {region['top']}) {region['width']}x{region['height']}",
            )

        self.monitor_center = None
        return None

    def _handle_region_selected(
        self,
        x: int,
        y: int,
        width: int,
        height: int,
        on_selected: Callable[[CaptureSelectionResult], None],
    ) -> None:
        self.overlay_active = False
        on_selected(self.apply_region_selection(x, y, width, height))

    def _handle_center_selected(
        self,
        x: int,
        y: int,
        on_selected: Callable[[CaptureSelectionResult], None],
    ) -> None:
        self.center_selector_active = False
        on_selected(self.apply_center_selection(x, y, self.app_context.monitor_size))

    def _clear_region_overlay(self, *_args) -> None:
        self.overlay_active = False
        self.overlay = None

    def _clear_center_selector(self, *_args) -> None:
        self.center_selector_active = False
        self.center_selector = None
