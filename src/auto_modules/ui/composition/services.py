from __future__ import annotations

from dataclasses import dataclass

from auto_modules.core.mapping import MapStitcher
from auto_modules.adapters.platform import SquareScreenCapture
from auto_modules.core.routing import PathFinder
from auto_modules.core.vision import HSVRecognizer, PlayerTracker


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
