"""Side-effect adapter contracts for the vision process."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Callable, Protocol

import cv2
import numpy as np


def _wall_clock_ms() -> int:
    return int(time.time() * 1000)


@dataclass(frozen=True, slots=True)
class CapturedFrame:
    generation: int
    sequence: int
    captured_at_ms: int
    map_instance: str
    payload: bytes


class FrameCapture(Protocol):
    def capture(self) -> CapturedFrame | None: ...


class FrameProcessor(Protocol):
    def process(self, frame: CapturedFrame) -> Any: ...


class ImageProvider(Protocol):
    def __call__(self) -> np.ndarray | None: ...


class EncodedImageCapture:
    """Adapt an injected BGR image provider to ``CapturedFrame`` bytes.

    The provider remains responsible for the actual screenshot backend.  This
    adapter only validates the returned image and encodes it inside the
    capture process, keeping the cross-process contract compact and
    pickle-safe.  ``provider`` should be a top-level callable or a
    spawn-safe object when used with ``VisionProcessHandle``.
    """

    def __init__(
        self,
        provider: ImageProvider | Callable[[], np.ndarray | None],
        *,
        generation: int,
        map_instance: str,
        image_format: str = ".png",
        clock_ms: Callable[[], int] | None = None,
    ) -> None:
        if int(generation) <= 0 or not str(map_instance).strip():
            raise ValueError("generation and map_instance are required")
        normalized_format = str(image_format).strip().lower()
        if normalized_format not in {".png", ".jpg", ".jpeg"}:
            raise ValueError("image_format must be .png, .jpg, or .jpeg")
        self.provider = provider
        self.generation = int(generation)
        self.map_instance = str(map_instance).strip()
        self.image_format = ".jpg" if normalized_format == ".jpeg" else normalized_format
        self.clock_ms = clock_ms or _wall_clock_ms
        self._sequence = 0

    def capture(self) -> CapturedFrame | None:
        image = self.provider()
        if image is None:
            return None
        array = np.asarray(image)
        if array.ndim != 3 or array.shape[2] < 3 or array.shape[0] <= 0 or array.shape[1] <= 0:
            raise ValueError("image provider must return a non-empty BGR image")
        bgr = np.ascontiguousarray(array[:, :, :3], dtype=np.uint8)
        encoded_ok, encoded = cv2.imencode(self.image_format, bgr)
        if not encoded_ok or encoded.size == 0:
            raise RuntimeError("unable to encode captured image")
        self._sequence += 1
        return CapturedFrame(
            generation=self.generation,
            sequence=self._sequence,
            captured_at_ms=max(0, int(self.clock_ms())),
            map_instance=self.map_instance,
            payload=encoded.tobytes(),
        )

    def close(self) -> None:
        """Close an optional provider resource without owning its lifecycle."""

        close = getattr(self.provider, "close", None)
        if callable(close):
            close()

    def rebind_session(self, *, generation: int, map_instance: str) -> None:
        """Reset the capture header when a handle is intentionally reused."""

        if int(generation) <= 0 or not str(map_instance).strip():
            raise ValueError("generation and map instance are required")
        self.generation = int(generation)
        self.map_instance = str(map_instance).strip()
        self._sequence = 0


__all__ = ["CapturedFrame", "EncodedImageCapture", "FrameCapture", "FrameProcessor", "ImageProvider"]
