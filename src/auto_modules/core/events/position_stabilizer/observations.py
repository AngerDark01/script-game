from __future__ import annotations

from ..debug import event_log
from ..models import EventDetection, EventObservation
from .models import PositionCluster


def stable_observation(
    cluster: PositionCluster,
    detection: EventDetection,
    event_config: dict,
    now_ms: int,
    should_log,
) -> EventObservation | None:
    required_samples = max(
        1,
        int(event_config.get("stable_frames", event_config.get("localization_samples", event_config.get("confirm_frames", 3)))),
    )
    max_variance = float(event_config.get("stable_variance", event_config.get("localization_max_variance", 1600.0)))
    emit_interval_ms = int(event_config.get("localization_emit_interval_ms", 700))
    variance = cluster.variance()

    if len(cluster.samples) < required_samples:
        return None
    if variance > max_variance:
        if should_log(f"unstable:{id(cluster)}", now_ms, 1000):
            center = cluster.center()
            event_log(
                "event localization unstable",
                event=cluster.event_type,
                samples=len(cluster.samples),
                required=required_samples,
                variance=float(variance),
                max_variance=float(max_variance),
                center=(int(round(center[0])), int(round(center[1]))),
            )
        return None
    if cluster.last_emitted_ms and now_ms - cluster.last_emitted_ms < emit_interval_ms:
        return None

    cluster.last_emitted_ms = int(now_ms)
    center = cluster.center()
    latest = cluster.samples[-1]
    event_log(
        "event localization stable",
        event=cluster.event_type,
        samples=len(cluster.samples),
        global_pos=(int(round(center[0])), int(round(center[1]))),
        variance=float(variance),
        conf=float(cluster.confidence()),
    )
    return EventObservation(
        event_type=cluster.event_type,
        confidence=cluster.confidence(),
        observed_at_ms=int(now_ms),
        global_pos=(int(round(center[0])), int(round(center[1]))),
        local_minimap_pos=latest.local_pos,
        source=f"{detection.source}+wall_registration",
        sample_count=len(cluster.samples),
        variance=float(variance),
        metadata={
            **latest.metadata,
            "localization_samples": len(cluster.samples),
            "localization_variance": float(variance),
            "localization_sources": sorted({sample.source for sample in cluster.samples}),
        },
    )
