"""Bridge legacy event observations to the shared perception contract.

This module intentionally contains no detector or game policy.  It only
translates the event runtime's minimap-local result shape to and from the
generic target-detection shape so the two systems can share a composition
seam without changing their algorithms.
"""

from __future__ import annotations

import copy
import math
from collections.abc import Iterable
from typing import Any

from core.perception.models import BoundingBox, CoordinateSpace, TargetDetection

from .models import EventDetection


def event_detection_to_target_detection(detection: EventDetection) -> TargetDetection:
    """Represent one legacy minimap event as an immutable generic detection.

    The event type becomes ``target_type``.  Metadata is deep-copied so debug
    consumers cannot mutate a detector-owned event through the generic view.
    A valid legacy ``metadata['bbox']`` is additionally exposed as the shared
    ``BoundingBox`` field while remaining in metadata for lossless round trips.
    """

    metadata = _copied_metadata(detection.metadata)
    point = _minimap_point(detection.local_minimap_pos, field_name="local_minimap_pos")
    return TargetDetection(
        target_type=str(detection.event_type),
        center=point,
        coordinate_space=CoordinateSpace.MINIMAP,
        confidence=float(detection.confidence),
        bbox=_bbox_from_metadata(metadata),
        source=str(detection.source),
        detected_at_ms=int(detection.detected_at_ms),
        text=_metadata_text(metadata),
        metadata=metadata,
    )


def target_detection_to_event_detection(
    detection: TargetDetection,
    *,
    event_type: str,
) -> EventDetection:
    """Adapt an explicitly classified minimap target for the legacy runtime.

    ``event_type`` is deliberately required: a generic target class alone does
    not opt it into an event workflow.  The caller chooses the event definition
    whose stabilization, memory, and handler policies will consume the result.
    """

    if detection.coordinate_space != CoordinateSpace.MINIMAP:
        raise ValueError(
            "event detections require CoordinateSpace.MINIMAP; "
            f"received {detection.coordinate_space.value!r}"
        )
    normalized_event_type = str(event_type).strip()
    if not normalized_event_type:
        raise ValueError("event_type must not be empty")

    metadata = _copied_metadata(detection.metadata)
    if detection.bbox is not None and "bbox" not in metadata:
        metadata["bbox"] = _bbox_to_metadata(detection.bbox)
    if detection.text is not None and "text" not in metadata:
        metadata["text"] = str(detection.text)
    center = _minimap_point(detection.center, field_name="center")
    return EventDetection(
        event_type=normalized_event_type,
        confidence=float(detection.confidence),
        detected_at_ms=int(detection.detected_at_ms or 0),
        local_minimap_pos=(int(round(center[0])), int(round(center[1]))),
        source=str(detection.source),
        metadata=metadata,
    )


def normalize_legacy_event_detections(
    detections: Iterable[EventDetection],
) -> tuple[tuple[EventDetection, ...], tuple[TargetDetection, ...]]:
    """Run legacy event results through the shared schema without changing order.

    Returns the reconstructed legacy detections first for the existing event
    runtime, then their generic counterparts for UI, diagnostics, or a future
    perception producer.  The two sequences own independent metadata copies.
    """

    normalized: list[EventDetection] = []
    targets: list[TargetDetection] = []
    for legacy_detection in detections:
        target_detection = event_detection_to_target_detection(legacy_detection)
        targets.append(target_detection)
        normalized.append(
            target_detection_to_event_detection(
                target_detection,
                event_type=legacy_detection.event_type,
            )
        )
    return tuple(normalized), tuple(targets)


def _copied_metadata(metadata: dict[str, Any] | None) -> dict[str, Any]:
    return copy.deepcopy(dict(metadata or {}))


def _minimap_point(point: tuple[float, float], *, field_name: str) -> tuple[float, float]:
    if not isinstance(point, (tuple, list)) or len(point) != 2:
        raise ValueError(f"{field_name} must contain exactly two coordinates")
    x, y = float(point[0]), float(point[1])
    if not math.isfinite(x) or not math.isfinite(y):
        raise ValueError(f"{field_name} coordinates must be finite")
    return x, y


def _bbox_from_metadata(metadata: dict[str, Any]) -> BoundingBox | None:
    raw_bbox = metadata.get("bbox")
    if not isinstance(raw_bbox, (list, tuple)) or len(raw_bbox) != 4:
        return None
    try:
        left, top, width, height = (float(value) for value in raw_bbox)
    except (TypeError, ValueError):
        return None
    if not all(math.isfinite(value) for value in (left, top, width, height)):
        return None
    return BoundingBox(left=left, top=top, width=width, height=height)


def _bbox_to_metadata(bbox: BoundingBox) -> list[float]:
    return [float(bbox.left), float(bbox.top), float(bbox.width), float(bbox.height)]


def _metadata_text(metadata: dict[str, Any]) -> str | None:
    text = metadata.get("text")
    return str(text) if text is not None else None
