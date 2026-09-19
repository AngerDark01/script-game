"""Torchlight-specific navigation UI composition."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from auto_modules.adapters.windows.window_finder import find_game_window
from auto_modules.features.torchlight.composition import build_torchlight_feature_registry
from auto_modules.ui.modes.navigation.presentation import (
    EventCircleOverlay,
    EventOverlayContext,
)


@dataclass(frozen=True)
class TorchlightNavigationComposition:
    """Dependencies injected into the otherwise game-neutral navigation page."""

    event_registry_factory: Callable
    game_window_finder: Callable[[], object]
    event_overlay_providers: tuple[Callable[[EventOverlayContext], tuple], ...]


def build_torchlight_navigation_composition() -> TorchlightNavigationComposition:
    return TorchlightNavigationComposition(
        event_registry_factory=build_torchlight_feature_registry,
        game_window_finder=find_torchlight_window_rect,
        event_overlay_providers=(build_loot_debug_overlays,),
    )


def find_torchlight_window_rect():
    """Return the current Torchlight client rectangle when it is available."""
    try:
        window = find_game_window("Torchlight", "UnrealWindow")
        return window.rect if window else None
    except Exception:
        return None


def build_loot_debug_overlays(context: EventOverlayContext) -> tuple[EventCircleOverlay, ...]:
    """Translate Torchlight loot-mask diagnostics into generic circle overlays."""
    config = _event_config(context.event_config, "loot")
    if not config or context.player_global_pos is None:
        return ()
    if not bool(config.get("enabled", True)):
        return ()
    if not bool(config.get("player_center_mask_enabled", True)):
        return ()
    if not bool(config.get("player_center_mask_overlay_enabled", True)):
        return ()

    radius = max(1.0, float(config.get("player_center_mask_radius", 28) or 28))
    return (
        EventCircleOverlay(
            global_pos=context.player_global_pos,
            scene_radius=radius * context.draw_scale,
            color="#00beff",
        ),
    )


def _event_config(event_config, event_type: str) -> dict:
    if event_config is None:
        return {}
    if hasattr(event_config, "event"):
        value = event_config.event(event_type)
    else:
        value = ((getattr(event_config, "events", {}) or {}).get(event_type) or {})
    return value if isinstance(value, dict) else {}


__all__ = [
    "TorchlightNavigationComposition",
    "build_loot_debug_overlays",
    "build_torchlight_navigation_composition",
    "find_torchlight_window_rect",
]
