from __future__ import annotations

from dataclasses import dataclass

from core.events.debug import event_log

from .loop import resolve_player_local_position
from .models import NavigationLocalizationResult


_LAST_CAPTURE_GEOMETRY_SIGNATURE: tuple | None = None


@dataclass(frozen=True)
class NavigationFrameTick:
    capture_rect: dict
    default_player_pos: tuple
    frame: object
    player_pos: tuple
    localization: NavigationLocalizationResult


def capture_navigation_localization_tick(
    *,
    build_capture_geometry,
    screen_capture,
    nav_config,
    nav_core,
    tracker,
    previous_player_local_pos,
) -> NavigationFrameTick | None:
    """Capture the current minimap frame and localize the player."""
    if not nav_config or (not nav_config.monitor_logical_center and not nav_config.monitor_region):
        return None

    capture_rect, default_player_pos = build_capture_geometry()
    if not capture_rect:
        return None

    frame = screen_capture.capture(
        capture_rect["left"],
        capture_rect["top"],
        capture_rect["width"],
        capture_rect["height"],
    )
    if frame is None:
        return None

    player_pos = resolve_player_local_position(
        nav_config=nav_config,
        nav_core=nav_core,
        tracker=tracker,
        frame=frame,
        capture_rect=capture_rect,
        default_player_pos=default_player_pos,
        previous_player_local_pos=previous_player_local_pos,
    )
    _log_capture_geometry_if_changed(
        nav_config=nav_config,
        capture_rect=capture_rect,
        default_player_pos=default_player_pos,
        player_pos=player_pos,
    )
    localization = NavigationLocalizationResult.from_core_result(
        nav_core.localize(frame, player_pos=player_pos)
    )
    return NavigationFrameTick(
        capture_rect=capture_rect,
        default_player_pos=default_player_pos,
        frame=frame,
        player_pos=player_pos,
        localization=localization,
    )


def _log_capture_geometry_if_changed(
    *,
    nav_config,
    capture_rect: dict,
    default_player_pos,
    player_pos,
) -> None:
    global _LAST_CAPTURE_GEOMETRY_SIGNATURE
    signature = (
        int(capture_rect.get("left", 0)),
        int(capture_rect.get("top", 0)),
        int(capture_rect.get("width", 0)),
        int(capture_rect.get("height", 0)),
        tuple(default_player_pos or ()),
        tuple(player_pos or ()),
        tuple(getattr(nav_config, "monitor_logical_center", None) or ()),
        bool(getattr(nav_config, "monitor_region", None)),
    )
    if signature == _LAST_CAPTURE_GEOMETRY_SIGNATURE:
        return
    _LAST_CAPTURE_GEOMETRY_SIGNATURE = signature
    event_log(
        "navigation capture geometry",
        capture_rect=dict(capture_rect or {}),
        monitor_logical_center=getattr(nav_config, "monitor_logical_center", None),
        monitor_region=getattr(nav_config, "monitor_region", None),
        monitor_size=getattr(nav_config, "monitor_size", None),
        default_player_pos=default_player_pos,
        player_pos=player_pos,
    )
