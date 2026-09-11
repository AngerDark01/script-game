"""Minimap adapters for existing perception frames and geometry operations."""
from dataclasses import replace
from threading import Lock

from core.perception.models import CoordinateSpace, FrameContext
from core.perception.preprocessing.geometry import crop
from core.perception.preprocessing.models import ImageArtifact, ImageGeometry


def crop_minimap(frame: FrameContext, *, left: int, top: int, width: int, height: int) -> FrameContext:
    h, w = frame.image.shape[:2]
    artifact = ImageArtifact(frame.image, frame, ImageGeometry.identity(
        width=w, height=h, coordinate_space=frame.coordinate_space))
    result = crop(artifact, left=left, top=top, width=width, height=height)
    return replace(frame, image=result.image, width=width, height=height,
                   coordinate_space=CoordinateSpace.MINIMAP,
                   metadata={**frame.metadata, 'source_geometry': result.geometry})


class LatestFrame:
    """Thread-local latest-value channel; no queue of stale images.

    Publishing transfers a snapshot of pixels. Multiprocess transport belongs to
    the runtime and must not try to pickle this lock.
    """
    def __init__(self):
        self._lock = Lock()
        self._frame = None

    def publish(self, frame: FrameContext) -> bool:
        if frame.captured_at_ms is None:
            raise ValueError('capture timestamp is required')
        with self._lock:
            if self._frame is not None and frame.captured_at_ms <= self._frame.captured_at_ms:
                return False
            pixels = frame.image.copy()
            pixels.setflags(write=False)
            self._frame = replace(frame, image=pixels)
            return True

    def read(self):
        with self._lock:
            return self._frame

    def clear(self):
        with self._lock:
            self._frame = None
