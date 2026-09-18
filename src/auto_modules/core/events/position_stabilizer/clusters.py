from __future__ import annotations

import math

from ..debug import event_log
from ..models import EventDetection
from .models import PositionCluster, PositionSample


def merge_sample(
    clusters: list[PositionCluster],
    detection: EventDetection,
    global_pos: tuple[float, float],
    event_config: dict,
    now_ms: int,
    should_log,
) -> PositionCluster:
    cluster_radius = float(event_config.get("localization_cluster_radius", event_config.get("dedupe_radius", 90)))
    cluster = find_cluster(clusters, detection.event_type, global_pos, cluster_radius, now_ms)
    if cluster is None:
        cluster = PositionCluster(event_type=detection.event_type)
        clusters.append(cluster)
        event_log(
            "event localization cluster created",
            event=detection.event_type,
            global_pos=(int(round(global_pos[0])), int(round(global_pos[1]))),
            source=detection.source,
            conf=float(detection.confidence),
        )

    cluster.samples.append(
        PositionSample(
            global_pos=global_pos,
            local_pos=(int(detection.local_minimap_pos[0]), int(detection.local_minimap_pos[1])),
            confidence=float(detection.confidence),
            seen_ms=int(detection.detected_at_ms),
            source=detection.source,
            metadata=dict(detection.metadata),
        )
    )
    cluster.last_seen_ms = int(now_ms)
    max_samples = max(3, int(event_config.get("localization_max_samples", 12)))
    if len(cluster.samples) > max_samples:
        cluster.samples = cluster.samples[-max_samples:]

    if should_log(f"cluster:{id(cluster)}", now_ms, 750):
        center = cluster.center()
        event_log(
            "event localization sample",
            event=detection.event_type,
            samples=len(cluster.samples),
            center=(int(round(center[0])), int(round(center[1]))),
            variance=float(cluster.variance()),
            conf=float(cluster.confidence()),
        )
    return cluster


def find_cluster(
    clusters: list[PositionCluster],
    event_type: str,
    global_pos: tuple[float, float],
    radius: float,
    now_ms: int,
) -> PositionCluster | None:
    best = None
    best_distance = None
    for cluster in clusters:
        if cluster.event_type != event_type or not cluster.samples:
            continue
        # Do not merge two icons detected in the same minimap frame. Paired
        # portals can be close together, but they must remain separate tasks.
        if cluster.last_seen_ms and cluster.last_seen_ms == int(now_ms):
            continue
        distance = _distance(cluster.center(), global_pos)
        if distance <= radius and (best_distance is None or distance < best_distance):
            best = cluster
            best_distance = distance
    return best


def expire_old_clusters(
    clusters: list[PositionCluster],
    config,
    now_ms: int,
) -> list[PositionCluster]:
    kept: list[PositionCluster] = []
    for cluster in clusters:
        event_config = config.event(cluster.event_type) if hasattr(config, "event") else {}
        ttl_ms = int(event_config.get("localization_cluster_ttl_ms", 12000))
        last_seen = cluster.samples[-1].seen_ms if cluster.samples else 0
        if now_ms - last_seen <= ttl_ms:
            kept.append(cluster)
    return kept


def _distance(a, b) -> float:
    return float(math.hypot(float(a[0]) - float(b[0]), float(a[1]) - float(b[1])))
