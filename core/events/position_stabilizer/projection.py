from __future__ import annotations

from ..models import EventDetection, FrameRegistration


def project_detection(
    detection: EventDetection,
    registration: FrameRegistration,
) -> tuple[float, float] | None:
    if detection.local_minimap_pos is None or registration.frame_origin_global is None:
        return None
    origin_x, origin_y = registration.frame_origin_global
    local_x, local_y = detection.local_minimap_pos
    scale = float(registration.draw_scale or 1.0)
    return float(origin_x) + float(local_x) * scale, float(origin_y) + float(local_y) * scale
