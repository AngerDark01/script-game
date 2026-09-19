"""Capture adapter bound only to the PoE2 monitor contract."""

from __future__ import annotations

from auto_modules.core.spatial.monitor_binding import MonitorBinding


class MonitorFrameSource:
    def __init__(self, capture_backend) -> None:
        self._capture_backend = capture_backend

    def capture(self, binding: MonitorBinding):
        if not isinstance(binding, MonitorBinding):
            raise TypeError("binding must be a MonitorBinding")
        rect = binding.rect
        return self._capture_backend.capture(rect.left, rect.top, rect.width, rect.height)


__all__ = ["MonitorFrameSource"]
