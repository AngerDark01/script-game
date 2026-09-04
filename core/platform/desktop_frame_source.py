"""Whole-desktop capture with explicit physical desktop geometry metadata."""

from __future__ import annotations

import ctypes
import os
import time
from typing import Any, Callable, Protocol

from core.perception.models import CoordinateSpace, FrameContext
from core.spatial.desktop_mapping import ScreenGeometry

from .screen_capture import SquareScreenCapture


class DesktopGeometryProvider(Protocol):
    """Expose the current physical desktop rectangle used by input injection."""

    def current_geometry(self) -> ScreenGeometry: ...


class WindowsDesktopGeometryProvider:
    """Read virtual desktop bounds through Win32 after best-effort DPI awareness."""

    _SM_XVIRTUALSCREEN = 76
    _SM_YVIRTUALSCREEN = 77
    _SM_CXVIRTUALSCREEN = 78
    _SM_CYVIRTUALSCREEN = 79

    def __init__(self) -> None:
        if os.name != "nt":
            raise RuntimeError("WindowsDesktopGeometryProvider requires Windows")
        self._user32 = ctypes.windll.user32
        self._set_dpi_awareness()

    def current_geometry(self) -> ScreenGeometry:
        """Return virtual-screen physical bounds and the system DPI observation."""
        left = self._user32.GetSystemMetrics(self._SM_XVIRTUALSCREEN)
        top = self._user32.GetSystemMetrics(self._SM_YVIRTUALSCREEN)
        width = self._user32.GetSystemMetrics(self._SM_CXVIRTUALSCREEN)
        height = self._user32.GetSystemMetrics(self._SM_CYVIRTUALSCREEN)
        dpi = self._system_dpi()
        return ScreenGeometry(
            left=left,
            top=top,
            width=width,
            height=height,
            dpi_scale_x=dpi / 96.0,
            dpi_scale_y=dpi / 96.0,
        )

    def _set_dpi_awareness(self) -> None:
        """Request per-monitor DPI coordinates without failing an already-aware host."""
        try:
            setter = self._user32.SetProcessDpiAwarenessContext
            setter.argtypes = [ctypes.c_void_p]
            setter.restype = ctypes.c_bool
            setter(ctypes.c_void_p(-4))  # DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2
            return
        except (AttributeError, OSError):
            pass
        try:
            legacy_setter = self._user32.SetProcessDPIAware
            legacy_setter.restype = ctypes.c_bool
            legacy_setter()
        except (AttributeError, OSError):
            pass

    def _system_dpi(self) -> int:
        try:
            getter = self._user32.GetDpiForSystem
            getter.restype = ctypes.c_uint
            dpi = int(getter())
            return dpi if dpi > 0 else 96
        except (AttributeError, OSError):
            return 96


class DesktopFrameSource:
    """Capture a whole desktop and pair its source image with destination geometry."""

    def __init__(
        self,
        *,
        geometry_provider: DesktopGeometryProvider | None = None,
        capture_backend: Callable[[ScreenGeometry], Any] | None = None,
    ) -> None:
        self._geometry_provider = geometry_provider or WindowsDesktopGeometryProvider()
        self._capture_backend = capture_backend or _capture_desktop

    def capture(self) -> tuple[FrameContext, ScreenGeometry]:
        """Capture once and return a full-screen frame plus its observed geometry."""
        geometry = self._geometry_provider.current_geometry()
        if not isinstance(geometry, ScreenGeometry):
            raise TypeError("geometry_provider must return ScreenGeometry")
        image = self._capture_backend(geometry)
        shape = getattr(image, "shape", None)
        if shape is None or len(shape) < 2:
            raise TypeError("desktop capture backend must return an array-like image")
        height, width = int(shape[0]), int(shape[1])
        if width <= 0 or height <= 0:
            raise ValueError("desktop capture backend returned an empty image")
        return (
            FrameContext(
                image=image,
                captured_at_ms=int(time.monotonic() * 1000),
                source="desktop_frame_source",
                width=width,
                height=height,
                coordinate_space=CoordinateSpace.FULL_SCREEN,
                metadata={
                    "physical_desktop": {
                        "left": geometry.left,
                        "top": geometry.top,
                        "width": geometry.width,
                        "height": geometry.height,
                    },
                    "dpi_scale_x": geometry.dpi_scale_x,
                    "dpi_scale_y": geometry.dpi_scale_y,
                },
            ),
            geometry,
        )


def _capture_desktop(geometry: ScreenGeometry) -> Any:
    """Capture the exact geometry rectangle using the existing platform backend."""
    capture = SquareScreenCapture()
    try:
        return capture.capture(
            int(geometry.left),
            int(geometry.top),
            int(geometry.width),
            int(geometry.height),
        )
    finally:
        capture.close()
