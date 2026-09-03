from __future__ import annotations

from dataclasses import dataclass

from core.mapping import MapStitcher
from core.platform import SquareScreenCapture
from core.routing import PathFinder
from core.vision import HSVRecognizer, PlayerTracker


@dataclass(frozen=True)
class CoreServices:
    screen_capture: SquareScreenCapture
    recognizer: HSVRecognizer
    stitcher: MapStitcher
    tracker: PlayerTracker
    path_finder: PathFinder


def create_core_services(*, canvas_size: int = 5000) -> CoreServices:
    """Create the default core services used by the GUI application."""
    return CoreServices(
        screen_capture=SquareScreenCapture(),
        recognizer=HSVRecognizer(),
        stitcher=MapStitcher(canvas_size=canvas_size),
        tracker=PlayerTracker(),
        path_finder=PathFinder(),
    )
