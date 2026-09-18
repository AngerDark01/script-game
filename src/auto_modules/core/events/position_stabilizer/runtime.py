from __future__ import annotations

from typing import Iterable

from ..debug import event_log
from ..models import EventDetection, EventObservation, FrameRegistration
from .clusters import expire_old_clusters, find_cluster, merge_sample
from .models import PositionCluster
from .observations import stable_observation
from .projection import project_detection


class EventPositionStabilizer:
    """Projects local event detections through wall registration and fuses frames."""

    def __init__(self):
        self._clusters: list[PositionCluster] = []
        self._last_log_ms: dict[str, int] = {}

    def clear_event_type(self, event_type: str, now_ms: int | None = None) -> int:
        before = len(self._clusters)
        self._clusters = [cluster for cluster in self._clusters if cluster.event_type != event_type]
        removed = before - len(self._clusters)
        self._last_log_ms = {
            key: value
            for key, value in self._last_log_ms.items()
            if f":{event_type}" not in key
        }
        event_log(
            "event localization clusters cleared",
            event=event_type,
            removed=removed,
            now_ms=int(now_ms or 0),
        )
        return removed

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
        return project_detection(detection, registration)

    def _merge_sample(
        self,
        detection: EventDetection,
        global_pos: tuple[float, float],
        event_config: dict,
        now_ms: int,
    ) -> PositionCluster:
        return merge_sample(self._clusters, detection, global_pos, event_config, now_ms, self._should_log)

    def _stable_observation(
        self,
        cluster: PositionCluster,
        detection: EventDetection,
        event_config: dict,
        now_ms: int,
    ) -> EventObservation | None:
        return stable_observation(cluster, detection, event_config, now_ms, self._should_log)

    def _find_cluster(
        self,
        event_type: str,
        global_pos: tuple[float, float],
        radius: float,
        now_ms: int,
    ) -> PositionCluster | None:
        return find_cluster(self._clusters, event_type, global_pos, radius, now_ms)

    def _expire_old_clusters(self, config, now_ms: int) -> None:
        self._clusters = expire_old_clusters(self._clusters, config, now_ms)

    def _should_log(self, key: str, now_ms: int, interval_ms: int) -> bool:
        last_ms = self._last_log_ms.get(key)
        if last_ms is not None and now_ms - last_ms < interval_ms:
            return False
        self._last_log_ms[key] = int(now_ms)
        return True
