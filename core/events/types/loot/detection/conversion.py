from __future__ import annotations

from core.events.models import EventDetection

from .models import LootCluster


def clusters_to_detections(
    event_type: str,
    clusters: list[LootCluster],
    now_ms: int,
    *,
    source: str = "minimap_weighted_blob",
    pickup_radius: int | None = None,
) -> list[EventDetection]:
    detections: list[EventDetection] = []
    for cluster in clusters:
        detections.append(
            EventDetection(
                event_type=event_type,
                confidence=float(cluster.score),
                detected_at_ms=int(now_ms),
                local_minimap_pos=(int(cluster.center[0]), int(cluster.center[1])),
                source=source,
                metadata={
                    "detector": "weighted_blob",
                    "bbox": [int(cluster.bbox[0]), int(cluster.bbox[1]), int(cluster.bbox[2]), int(cluster.bbox[3])],
                    "candidate_count": int(cluster.candidates),
                    "templates": list(cluster.templates),
                    "template_score": float(cluster.template_score),
                    "shape_score": float(cluster.shape_score),
                    "color_score": float(cluster.color_score),
                    "pickup_radius": int(pickup_radius) if pickup_radius is not None else None,
                },
            )
        )
    return detections
