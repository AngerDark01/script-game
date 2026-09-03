from __future__ import annotations

from core.localization.frame_registration import (
    build_frame_registration,
    clear_frame_registration,
)


def clear_navigation_frame_registration(nav_core, confidence=0.0, source="failed") -> None:
    """Write an invalid frame-registration snapshot to the NavigationCore."""
    nav_core.last_frame_registration = clear_frame_registration(
        nav_core.draw_scale,
        confidence,
        source,
    )


def set_navigation_frame_registration(
    nav_core,
    player_global_pos,
    player_local_pos,
    frame_shape,
    confidence,
    source,
    metadata=None,
) -> None:
    """Write a valid frame-registration snapshot to the NavigationCore."""
    nav_core.last_frame_registration = build_frame_registration(
        draw_scale=nav_core.draw_scale,
        player_global_pos=player_global_pos,
        player_local_pos=player_local_pos,
        frame_shape=frame_shape,
        confidence=confidence,
        source=source,
        metadata=metadata,
    )
