from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Iterable

from .debug import event_log
from .models import EventDetection, EventObservation, FrameRegistration


@dataclass
class _PositionSample:
    global_pos: tuple[float, float]
    local_pos: tuple[int, int]
    confidence: float
    seen_ms: int
    source: str
    metadata: dict


@dataclass
class _PositionCluster:
    event_type: str
    samples: list[_PositionSample] = field(default_factory=list)
    last_emitted_ms: int = 0
    last_seen_ms: int = 0

    def center(self) -> tuple[float, float]:
        total_weight = sum(max(0.01, sample.confidence) for sample in self.samples)
        if total_weight <= 0:
            return self.samples[-1].global_pos
        x = sum(sample.global_pos[0] * max(0.01, sample.confidence) for sample in self.samples) / total_weight
        y = sum(sample.global_pos[1] * max(0.01, sample.confidence) for sample in self.samples) / total_weight
        return x, y

    def variance(self) -> float:
        if len(self.samples) <= 1:
            return 0.0
        cx, cy = self.center()
        return float(
            sum((sample.global_pos[0] - cx) ** 2 + (sample.global_pos[1] - cy) ** 2 for sample in self.samples)
            / len(self.samples)
        )

    def confidence(self) -> float:
        if not self.samples:
            return 0.0
        return float(max(sample.confidence for sample in self.samples))


class EventPositionStabilizer:
    """Projects local event detections through wall registration and fuses frames."""

    def __init__(self):
        self._clusters: list[_PositionCluster] = []
        self._last_log_ms: dict[str, int] = {}

    def update(
        self,
        detections: Iterable[EventDetection],
        registration: FrameRegistration | None,
        config,
        now_ms: int,
    ) -> list[EventObservation]:
        if not registration or not registration.valid or registration.frame_origin_global is None:
            if self._should_log("no_registration", now_ms, 1500):
                event_log(
                    "event localization skipped",
                    reason="no valid frame registration",
                    source=getattr(registration, "source", None),
                    conf=float(getattr(registration, "confidence", 0.0) or 0.0),
                )
            return []

        observations: list[EventObservation] = []
        for detection in detections:
            event_config = config.event(detection.event_type) if hasattr(config, "event") else {}
            if not event_config.get("enabled", True):
                continue
            projected = self._project(detection, registration)
            if projected is None:
                continue
            cluster = self._merge_sample(detection, projected, event_config, now_ms)
            observation = self._stable_observation(cluster, detection, event_config, now_ms)
            if observation is not None:
                observations.append(observation)

        self._expire_old_clusters(config, now_ms)
        return observations

    def _project(
        self,
        detection: EventDetection,
        registration: FrameRegistration,
    ) -> tuple[float, float] | None:
        if detection.local_minimap_pos is None or registration.frame_origin_global is None:
            return None
        origin_x, origin_y = registration.frame_origin_global
        local_x, local_y = detection.local_minimap_pos
        scale = float(registration.draw_scale or 1.0)
        return float(origin_x) + float(local_x) * scale, float(origin_y) + float(local_y) * scale

    def _merge_sample(
        self,
        detection: EventDetection,
        global_pos: tuple[float, float],
        event_config: dict,
        now_ms: int,
    ) -> _PositionCluster:
        cluster_radius = float(event_config.get("localization_cluster_radius", event_config.get("dedupe_radius", 90)))
        cluster = self._find_cluster(detection.event_type, global_pos, cluster_radius, now_ms)
        if cluster is None:
            cluster = _PositionCluster(event_type=detection.event_type)
            self._clusters.append(cluster)
            event_log(
                "event localization cluster created",
                event=detection.event_type,
                global_pos=(int(round(global_pos[0])), int(round(global_pos[1]))),
                source=detection.source,
                conf=float(detection.confidence),
            )

        cluster.samples.append(
            _PositionSample(
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

        if self._should_log(f"cluster:{id(cluster)}", now_ms, 750):
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

    def _stable_observation(
        self,
        cluster: _PositionCluster,
        detection: EventDetection,
        event_config: dict,
        now_ms: int,
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
            if self._should_log(f"unstable:{id(cluster)}", now_ms, 1000):
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

    def _find_cluster(
        self,
        event_type: str,
        global_pos: tuple[float, float],
        radius: float,
        now_ms: int,
    ) -> _PositionCluster | None:
        best = None
        best_distance = None
        for cluster in self._clusters:
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

    def _expire_old_clusters(self, config, now_ms: int) -> None:
        kept: list[_PositionCluster] = []
        for cluster in self._clusters:
            event_config = config.event(cluster.event_type) if hasattr(config, "event") else {}
            ttl_ms = int(event_config.get("localization_cluster_ttl_ms", 12000))
            last_seen = cluster.samples[-1].seen_ms if cluster.samples else 0
            if now_ms - last_seen <= ttl_ms:
                kept.append(cluster)
        self._clusters = kept

    def _should_log(self, key: str, now_ms: int, interval_ms: int) -> bool:
        last_ms = self._last_log_ms.get(key)
        if last_ms is not None and now_ms - last_ms < interval_ms:
            return False
        self._last_log_ms[key] = int(now_ms)
        return True


def _distance(a, b) -> float:
    return float(math.hypot(float(a[0]) - float(b[0]), float(a[1]) - float(b[1])))
