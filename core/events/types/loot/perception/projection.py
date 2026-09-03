from __future__ import annotations

from core.events.models import EventDetection

from .models import LootPerceptionRecord, RegistrationSnapshot


def snapshot_registration(registration) -> RegistrationSnapshot:
    return RegistrationSnapshot(
        valid=bool(getattr(registration, "valid", False)),
        frame_origin_global=getattr(registration, "frame_origin_global", None),
        draw_scale=float(getattr(registration, "draw_scale", 1.0) or 1.0),
        frame_size=getattr(registration, "frame_size", None),
        source=str(getattr(registration, "source", "") or ""),
    )


def local_to_global(local_pos: tuple[int, int], registration: RegistrationSnapshot) -> tuple[float, float] | None:
    if not registration.valid or registration.frame_origin_global is None:
        return None
    origin_x, origin_y = registration.frame_origin_global
    scale = max(1e-6, float(registration.draw_scale))
    return float(origin_x) + float(local_pos[0]) * scale, float(origin_y) + float(local_pos[1]) * scale


def global_to_local(global_pos: tuple[float, float], registration: RegistrationSnapshot) -> tuple[int, int] | None:
    if not registration.valid or registration.frame_origin_global is None:
        return None
    origin_x, origin_y = registration.frame_origin_global
    scale = max(1e-6, float(registration.draw_scale))
    local_x = int(round((float(global_pos[0]) - float(origin_x)) / scale))
    local_y = int(round((float(global_pos[1]) - float(origin_y)) / scale))
    frame_size = registration.frame_size
    if frame_size is not None:
        width, height = int(frame_size[0]), int(frame_size[1])
        if local_x < 0 or local_y < 0 or local_x >= width or local_y >= height:
            return None
    return local_x, local_y


def record_to_detection(
    record: LootPerceptionRecord,
    registration: RegistrationSnapshot,
    now_ms: int,
    *,
    event_type: str,
    pickup_radius: int,
) -> EventDetection | None:
    local_pos = global_to_local(record.global_pos, registration)
    if local_pos is None:
        return None
    width, height = record.bbox_size
    left = int(local_pos[0] - width / 2)
    top = int(local_pos[1] - height / 2)
    metadata = dict(record.metadata)
    metadata.update(
        {
            "detector": "async_feature_match",
            "bbox": [left, top, int(width), int(height)],
            "pickup_radius": int(pickup_radius),
            "perception_detected_at_ms": int(record.detected_at_ms),
            "perception_age_ms": max(0, int(now_ms) - int(record.detected_at_ms)),
            "perception_missing_streak": int(record.missing_streak),
        }
    )
    return EventDetection(
        event_type=event_type,
        confidence=float(record.confidence),
        detected_at_ms=int(now_ms),
        local_minimap_pos=(int(local_pos[0]), int(local_pos[1])),
        source="minimap_async_feature_match",
        metadata=metadata,
    )
