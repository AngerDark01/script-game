"""Spawn-safe PoE2 minimap capture and wall-mask adapters.

Only immutable monitor configuration crosses the Windows ``spawn`` boundary.
The screen backend and HSV recognizer are created lazily inside the worker
process, so Qt objects, MSS handles and CLAHE state never get pickled.
"""

from __future__ import annotations

from typing import Any, Callable

import numpy as np

from auto_modules.adapters.platform.screen_capture import SquareScreenCapture
from auto_modules.core.spatial.capture_geometry import CaptureShape
from auto_modules.core.spatial.monitor_binding import MonitorBinding
from auto_modules.core.vision import HSVRecognizer
from auto_modules.features.poe2.live_terrain.monitor_source import MonitorFrameSource


def _default_screen_capture_factory() -> Any:
    return SquareScreenCapture()


class SpawnSafePoe2MonitorCapture:
    """Capture the configured monitor binding from inside the vision process."""

    def __init__(
        self,
        binding: MonitorBinding,
        *,
        shape: CaptureShape | str = CaptureShape.SQUARE,
        radius: float | None = None,
        backend_factory: Callable[[], Any] = _default_screen_capture_factory,
    ) -> None:
        if not isinstance(binding, MonitorBinding):
            raise TypeError("binding must be MonitorBinding")
        if not callable(backend_factory):
            raise TypeError("backend_factory must be callable")
        self.binding = binding
        self.shape = CaptureShape.coerce(shape)
        self.radius = None if radius is None else float(radius)
        self.backend_factory = backend_factory
        self._backend: Any | None = None
        self._source: MonitorFrameSource | None = None

    def __call__(self) -> np.ndarray:
        if self._source is None:
            self._backend = self.backend_factory()
            self._source = MonitorFrameSource(self._backend)
        frame = self._source.capture(self.binding, shape=self.shape, radius=self.radius)
        array = np.asarray(frame)
        if array.ndim != 3 or array.shape[2] < 3 or array.size == 0:
            raise ValueError("PoE2 monitor capture must return a non-empty color image")
        return np.ascontiguousarray(array[:, :, :3], dtype=np.uint8)

    def close(self) -> None:
        backend, self._backend = self._backend, None
        self._source = None
        close = getattr(backend, "close", None)
        if callable(close):
            close()


class Poe2WallMaskExtractor:
    """Recreate the configured wall recognizer inside the vision process.

    It intentionally calls ``extract_walls`` only.  The dual path must not
    subtract a player mask or inflate a collision footprint around either
    marker; marker extraction remains a separate processor stage.
    """

    def __init__(self, recognizer_params: dict[str, Any] | None = None) -> None:
        self.recognizer_params = dict(recognizer_params or {})
        self._recognizer: HSVRecognizer | None = None

    def __call__(self, image: np.ndarray) -> np.ndarray:
        if self._recognizer is None:
            recognizer = HSVRecognizer()
            if self.recognizer_params:
                recognizer.set_params(dict(self.recognizer_params))
            self._recognizer = recognizer
        mask = self._recognizer.extract_walls(image)
        array = np.asarray(mask)
        if array.ndim != 2 or array.shape != image.shape[:2]:
            raise ValueError("PoE2 wall extractor returned an invalid mask")
        return np.where(array > 0, 255, 0).astype(np.uint8, copy=False)


__all__ = ["Poe2WallMaskExtractor", "SpawnSafePoe2MonitorCapture"]
