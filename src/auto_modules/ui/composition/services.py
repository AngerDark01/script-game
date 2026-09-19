from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from auto_modules.core.mapping import MapStitcher
from auto_modules.adapters.platform import SquareScreenCapture
from auto_modules.core.routing import PathFinder
from auto_modules.core.vision import HSVRecognizer, PlayerTracker
from auto_modules.adapters.host.communication_adapter import HostCommunicationAdapter
from auto_modules.application.communication.manager import CommunicationManager


@dataclass(frozen=True)
class CoreServices:
    screen_capture: SquareScreenCapture
    recognizer: HSVRecognizer
    stitcher: MapStitcher
    tracker: PlayerTracker
    path_finder: PathFinder


@dataclass(frozen=True)
class CommunicationServices:
    """Process-scoped communication composition shared by business pages."""

    adapter: HostCommunicationAdapter
    manager: CommunicationManager


def create_communication_services(
    client_factory: Callable[[], Any] | None = None,
) -> CommunicationServices:
    """Build one Host adapter and manager for all embedded business features."""

    adapter = HostCommunicationAdapter(client_factory)
    return CommunicationServices(adapter=adapter, manager=CommunicationManager(adapter.transport))


def create_core_services(*, canvas_size: int = 5000) -> CoreServices:
    """Create the default core services used by the GUI application."""
    return CoreServices(
        screen_capture=SquareScreenCapture(),
        recognizer=HSVRecognizer(),
        stitcher=MapStitcher(canvas_size=canvas_size),
        tracker=PlayerTracker(),
        path_finder=PathFinder(),
    )
