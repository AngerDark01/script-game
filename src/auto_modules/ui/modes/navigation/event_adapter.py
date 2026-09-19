from __future__ import annotations

from collections.abc import Callable

from auto_modules.core.events.models import EventTick
from auto_modules.core.events.registry import EventRegistry


def create_default_event_registry(
    registry_factory: Callable[[], EventRegistry] | None = None,
) -> EventRegistry:
    """Build an event registry supplied by the application composition root.

    A standalone navigation widget receives an empty generic registry. The
    host application injects a composition factory when it wants concrete
    event features.
    """
    return registry_factory() if registry_factory is not None else EventRegistry()


def event_config_summary(event_config) -> str:
    return ",".join(
        f"{event_type}:{'on' if values.get('enabled', True) else 'off'}"
        for event_type, values in getattr(event_config, "events", {}).items()
    )


def build_event_tick(
    *,
    now_ms,
    frame,
    player_pos,
    localized_pos,
    confidence,
    nav_core,
    nav_config,
    map_name: str,
    capture_provider,
) -> EventTick:
    return EventTick(
        now_ms=now_ms,
        raw_minimap_frame=frame,
        player_global_pos=localized_pos,
        player_local_minimap_pos=player_pos,
        localization_confidence=float(confidence or 0.0),
        draw_scale=float(nav_core.draw_scale if nav_core else nav_config.draw_scale),
        map_name=map_name,
        capture_provider=capture_provider,
        frame_registration=getattr(nav_core, "last_frame_registration", None) if nav_core else None,
    )


def event_status_text(event_coordinator) -> str:
    if not event_coordinator:
        return ""
    return event_coordinator.status_summary()
