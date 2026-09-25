"""Capture adapter bound only to the PoE2 monitor contract."""

from __future__ import annotations

import numpy as np

from auto_modules.core.spatial.capture_geometry import CaptureShape, build_capture_mask
from auto_modules.core.spatial.monitor_binding import MonitorBinding


class MonitorFrameSource:
    def __init__(self, capture_backend) -> None:
        self._capture_backend = capture_backend

    def capture(
        self,
        binding: MonitorBinding,
        *,
        shape: CaptureShape | str = CaptureShape.SQUARE,
        radius: float | None = None,
    ):
        if not isinstance(binding, MonitorBinding):
            raise TypeError("binding must be a MonitorBinding")
        rect = binding.rect
        frame = self._capture_backend.capture(rect.left, rect.top, rect.width, rect.height)
        selected_shape = CaptureShape.coerce(shape)
        if selected_shape is CaptureShape.SQUARE:
            return frame
        array = np.asarray(frame)
        mask = build_capture_mask(rect.width, rect.height, selected_shape, radius=radius)
        if array.ndim == 2:
            return np.where(mask, array, 0)
        if array.ndim == 3:
            return np.where(mask[..., None], array, 0)
        raise ValueError("capture backend must return a 2D or 3D image array")


__all__ = ["MonitorFrameSource"]
