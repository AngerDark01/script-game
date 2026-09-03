from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from core.events.capture_provider import GameWindowCaptureProvider
from core.events.config import load_event_config
from core.events.coordinator import EventCoordinator
from core.events.debug import event_log

from .panel_adapter import summarize_event_config


@dataclass(frozen=True)
class NavigationEventSystemRuntime:
    event_config: object | None
    event_coordinator: object | None
    event_capture_provider: object | None


def initialize_navigation_event_system(
    *,
    map_folder_path: str | None,
    event_registry,
    screen_capture,
    window_finder: Callable[[], object],
    map_name: str,
    refresh_event_dialog: Callable[[], None],
) -> NavigationEventSystemRuntime:
    """Create event runtime objects for the currently loaded navigation map."""
    if not map_folder_path:
        return NavigationEventSystemRuntime(
            event_config=None,
            event_coordinator=None,
            event_capture_provider=None,
        )

    event_config = load_event_config(map_folder_path)
    event_coordinator = EventCoordinator(event_registry, event_config)
    event_capture_provider = GameWindowCaptureProvider(
        screen_capture,
        window_finder=window_finder,
    )
    refresh_event_dialog()
    event_log(
        "event system initialized",
        map=map_name,
        enabled=bool(getattr(event_config, "enabled", True)),
        events=summarize_event_config(event_config),
    )
    return NavigationEventSystemRuntime(
        event_config=event_config,
        event_coordinator=event_coordinator,
        event_capture_provider=event_capture_provider,
    )
