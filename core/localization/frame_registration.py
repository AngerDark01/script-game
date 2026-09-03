from __future__ import annotations

from core.shared.frame_registration import FrameRegistration


def clear_frame_registration(draw_scale, confidence=0.0, source="failed") -> FrameRegistration:
    """Build an invalid frame registration for the current localization frame."""
    return FrameRegistration(
        valid=False,
        confidence=float(confidence or 0.0),
        draw_scale=float(draw_scale),
        source=str(source),
    )


def build_frame_registration(
    *,
    draw_scale,
    player_global_pos,
    player_local_pos,
    frame_shape,
    confidence,
    source,
    metadata=None,
) -> FrameRegistration:
    """Build frame-to-global registration metadata from a localized player point."""
    if player_global_pos is None or player_local_pos is None:
        return clear_frame_registration(draw_scale, confidence, source)

    origin_x = float(player_global_pos[0]) - float(player_local_pos[0]) * float(draw_scale)
    origin_y = float(player_global_pos[1]) - float(player_local_pos[1]) * float(draw_scale)
    frame_size = None
    if frame_shape is not None and len(frame_shape) >= 2:
        frame_size = (int(frame_shape[1]), int(frame_shape[0]))

    return FrameRegistration(
        valid=True,
        confidence=float(confidence or 0.0),
        frame_origin_global=(origin_x, origin_y),
        draw_scale=float(draw_scale),
        player_global_pos=(float(player_global_pos[0]), float(player_global_pos[1])),
        player_local_minimap_pos=(int(player_local_pos[0]), int(player_local_pos[1])),
        source=str(source),
        frame_size=frame_size,
        metadata=dict(metadata or {}),
    )
