from __future__ import annotations

from core.events.models import EventTick
from core.events.registry import EventRegistry
from core.events.types.loot import LootEventDefinition
from core.events.types.portal import PortalEventDefinition
from core.events.window_finder import find_game_window


def create_default_event_registry() -> EventRegistry:
    registry = EventRegistry()
    registry.register(PortalEventDefinition())
    registry.register(LootEventDefinition())
    return registry


def event_config_summary(event_config) -> str:
    return ",".join(
        f"{event_type}:{'on' if values.get('enabled', True) else 'off'}"
        for event_type, values in getattr(event_config, "events", {}).items()
    )


def find_default_game_window_rect():
    try:
        window = find_game_window("Torchlight", "UnrealWindow")
        return window.rect if window else None
    except Exception:
        return None


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
