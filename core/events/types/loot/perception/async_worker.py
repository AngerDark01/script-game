from __future__ import annotations

import threading

import numpy as np

from core.events.debug import event_log

from ..detection.feature_match import FeatureLootMatcher
from ..detection.roi import BBox
from .models import LootPerceptionRecord, RegistrationSnapshot
from .projection import local_to_global, record_to_detection, snapshot_registration


class AsyncLootPerception:
    """Runs heavyweight loot feature matching outside the navigation frame path."""

    def __init__(self, event_type: str = "loot") -> None:
        self.event_type = str(event_type)
        self._lock = threading.Lock()
        self._running = False
        self._records: list[LootPerceptionRecord] = []
        self._last_submit_ms = -1
        self._last_result_ms = -1
        self._last_log_ms = 0

    def update_visibility(self, seeds: list[BBox], registration, config, now_ms: int) -> None:
        snapshot = snapshot_registration(registration)
        radius = max(8, int(getattr(config, "async_known_seed_radius", 72)))
        with self._lock:
            if not self._records:
                return
            kept: list[LootPerceptionRecord] = []
            for record in self._records:
                local_pos = record_to_local(record, snapshot)
                if local_pos is None:
                    kept.append(record)
                    continue
                if any(seed_near_point(seed, local_pos, radius) for seed in seeds):
                    record.missing_streak = 0
                    kept.append(record)
                    continue
                record.missing_streak += 1
                if record.missing_streak < max(1, int(getattr(config, "absence_confirm_frames", 2))):
                    kept.append(record)
            removed = len(self._records) - len(kept)
            self._records = kept
        if removed > 0 and self._should_log(now_ms, 750):
            event_log("loot async records removed absent", removed=int(removed), remaining=len(kept))

    def maybe_submit(
        self,
        *,
        frame: np.ndarray,
        registration,
        seeds: list[BBox],
        matcher: FeatureLootMatcher,
        config,
        now_ms: int,
    ) -> bool:
        snapshot = snapshot_registration(registration)
        if not snapshot.valid or snapshot.frame_origin_global is None:
            return False
        if not seeds:
            return False
        with self._lock:
            if self._running:
                return False
            if not self._should_start_scan_locked(config, now_ms):
                return False
            self._running = True
            self._last_submit_ms = int(now_ms)

        thread = threading.Thread(
            target=self._run,
            args=(frame.copy(), tuple(seeds), matcher, snapshot, config, int(now_ms)),
            name="loot-perception-worker",
            daemon=True,
        )
        thread.start()
        return True

    def detections(self, registration, config, now_ms: int) -> list:
        snapshot = snapshot_registration(registration)
        ttl_ms = max(1, int(getattr(config, "async_track_ttl_ms", 8000)))
        pickup_radius = int(getattr(config, "pickup_radius", 58))
        result = []
        with self._lock:
            records = [
                record
                for record in self._records
                if int(now_ms) - int(record.detected_at_ms) <= ttl_ms
            ]
            self._records = records
        for record in records:
            detection = record_to_detection(
                record,
                snapshot,
                now_ms,
                event_type=self.event_type,
                pickup_radius=pickup_radius,
            )
            if detection is not None:
                result.append(detection)
        return result

    def clear(self) -> None:
        with self._lock:
            self._records = []
            self._last_result_ms = -1

    def _run(
        self,
        frame: np.ndarray,
        seeds: tuple[BBox, ...],
        matcher: FeatureLootMatcher,
        registration: RegistrationSnapshot,
        config,
        now_ms: int,
    ) -> None:
        try:
            clusters = matcher.detect(frame, list(seeds))
            records = records_from_clusters(clusters, registration, config, now_ms)
        except Exception as exc:  # pragma: no cover - defensive runtime boundary
            records = []
            event_log("loot async perception failed", error=repr(exc))
        with self._lock:
            self._records = merge_records(self._records, records, config)
            self._last_result_ms = int(now_ms)
            self._running = False
        if self._should_log(now_ms, 750):
            event_log("loot async perception result", records=len(records), cached=len(self._records))

    def _should_start_scan_locked(self, config, now_ms: int) -> bool:
        interval_ms = max(0, int(getattr(config, "async_full_scan_interval_ms", 1000)))
        if self._last_submit_ms >= 0 and int(now_ms) - int(self._last_submit_ms) < interval_ms:
            return False
        refresh_ms = max(1, int(getattr(config, "async_track_refresh_ms", 8000)))
        if self._records and self._last_result_ms >= 0 and int(now_ms) - int(self._last_result_ms) < refresh_ms:
            return False
        return True

    def _should_log(self, now_ms: int, interval_ms: int) -> bool:
        if int(now_ms) - int(self._last_log_ms) < int(interval_ms):
            return False
        self._last_log_ms = int(now_ms)
        return True


def records_from_clusters(clusters, registration: RegistrationSnapshot, config, now_ms: int) -> list[LootPerceptionRecord]:
    records: list[LootPerceptionRecord] = []
    for cluster in clusters:
        global_pos = local_to_global(cluster.center, registration)
        if global_pos is None:
            continue
        records.append(
            LootPerceptionRecord(
                confidence=float(cluster.score),
                global_pos=global_pos,
                source_local_pos=(int(cluster.center[0]), int(cluster.center[1])),
                bbox_size=(int(cluster.bbox[2]), int(cluster.bbox[3])),
                detected_at_ms=int(now_ms),
                metadata={
                    "candidate_count": int(cluster.candidates),
                    "templates": list(cluster.templates),
                    "template_score": float(cluster.template_score),
                    "shape_score": float(cluster.shape_score),
                    "color_score": float(cluster.color_score),
                    "feature_match_threshold": float(getattr(config, "feature_match_threshold", 0.64)),
                },
            )
        )
    return records


def merge_records(existing: list[LootPerceptionRecord], new_records: list[LootPerceptionRecord], config) -> list[LootPerceptionRecord]:
    if not new_records:
        return []
    radius = max(8.0, float(getattr(config, "dedupe_radius", 110)))
    merged = list(existing)
    for record in new_records:
        target = None
        for kept in merged:
            if global_distance(record.global_pos, kept.global_pos) <= radius:
                target = kept
                break
        if target is None:
            merged.append(record)
        else:
            target.confidence = max(float(target.confidence), float(record.confidence))
            target.global_pos = record.global_pos
            target.source_local_pos = record.source_local_pos
            target.bbox_size = record.bbox_size
            target.detected_at_ms = record.detected_at_ms
            target.metadata.update(record.metadata)
            target.missing_streak = 0
    merged.sort(key=lambda item: item.confidence, reverse=True)
    return merged[: max(1, int(getattr(config, "max_blobs_per_frame", 3)))]


def record_to_local(record: LootPerceptionRecord, registration: RegistrationSnapshot) -> tuple[int, int] | None:
    from .projection import global_to_local

    return global_to_local(record.global_pos, registration)


def seed_near_point(seed: BBox, point: tuple[int, int], radius: int) -> bool:
    x, y, width, height = seed
    cx = float(x + width / 2)
    cy = float(y + height / 2)
    return float(np.hypot(float(point[0]) - cx, float(point[1]) - cy)) <= float(radius)


def global_distance(a: tuple[float, float], b: tuple[float, float]) -> float:
    return float(np.hypot(float(a[0]) - float(b[0]), float(a[1]) - float(b[1])))
