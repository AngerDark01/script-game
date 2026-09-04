"""Platform adapters for screen capture and window integration."""

from .screen_capture import SquareScreenCapture
from .desktop_frame_source import DesktopFrameSource, DesktopGeometryProvider, WindowsDesktopGeometryProvider

__all__ = [
    "DesktopFrameSource",
    "DesktopGeometryProvider",
    "SquareScreenCapture",
    "WindowsDesktopGeometryProvider",
]
