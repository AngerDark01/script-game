from __future__ import annotations

import copy
import threading
import time
from dataclasses import dataclass

from core.events.config_model import EventSystemConfig
from core.events.debug import event_log
from core.events.models import EventTick


@dataclass(frozen=True)
class AsyncEventDetectionResult:
    tick: EventTick
    detections: list
    sequence: int
    submitted_at_ms: int
    started_at_ms: int
    finished_at_ms: int
    queue_ms: float
    detect_ms: float
    detect_cpu_ms: float
    dropped_before_start: int
    error: str = ""

    @property
    def total_ms(self) -> float:
        return max(0.0, float(self.finished_at_ms - self.submitted_at_ms))

    def age_ms(self) -> int:
        return max(0, int(time.time() * 1000) - int(self.finished_at_ms))


class AsyncEventObserver:
    """Run raw event detection on a latest-frame worker thread.

    The worker only calls detector code. Stabilization, memory merge, scheduler
    selection, handlers, and GUI updates stay on the navigation thread.
    """

    def __init__(self, coordinator, *, name: str = "event-detector") -> None:
        self.coordinator = coordinator
        self.name = str(name or "event-detector")
        self._condition = threading.Condition()
        self._pending: tuple[EventTick, EventSystemConfig, int, float, int, int] | None = None
        self._latest_result: AsyncEventDetectionResult | None = None
        self._closed = False
        self._dropped_pending = 0
        self._throttled_submit = 0
        self._submitted = 0
        self._completed = 0
        self._discard_before_sequence = 0
        self._last_submit_perf = 0.0
        self._last_result_log_ms = 0
        self._last_logged_dropped = 0
        self._slow_detect_ms = 80.0
        self._slow_queue_ms = 80.0
        self._result_log_interval_ms = 1000
        self._thread = threading.Thread(target=self._run, name=self.name, daemon=True)
        self._thread.start()
        event_log("async event observer started", name=self.name)

    def submit(self, tick: EventTick, config) -> None:
        if tick is None or tick.raw_minimap_frame is None:
            return
        if not getattr(config, "enabled", True):
            return

        submitted_perf = time.perf_counter()
        interval_ms = _observer_interval_ms(config)
        with self._condition:
            if self._closed:
                return
            if (
                interval_ms > 0
                and self._last_submit_perf > 0.0
                and (submitted_perf - self._last_submit_perf) * 1000.0 < float(interval_ms)
            ):
                self._throttled_submit += 1
                return
            self._last_submit_perf = submitted_perf

        worker_tick = clone_event_tick(tick)
        config_snapshot = snapshot_event_config(config)
        submitted_at_ms = int(time.time() * 1000)

        with self._condition:
            if self._closed:
                return
            if self._pending is not None:
                self._dropped_pending += 1
            self._submitted += 1
            sequence = int(self._submitted)
            self._pending = (
                worker_tick,
                config_snapshot,
                submitted_at_ms,
                submitted_perf,
                self._dropped_pending,
                sequence,
            )
            self._condition.notify()

    def poll(self, *, max_age_ms: int | None = None) -> AsyncEventDetectionResult | None:
        with self._condition:
            result = self._latest_result
            self._latest_result = None
        if result is not None:
            if max_age_ms is not None and result.age_ms() > int(max_age_ms):
                event_log(
                    "async event detection result discarded",
                    name=self.name,
                    seq=result.sequence,
                    detections=len(result.detections),
                    result_age_ms=result.age_ms(),
                    max_age_ms=int(max_age_ms),
                    detect_ms=round(float(result.detect_ms), 2),
                    detect_cpu_ms=round(float(result.detect_cpu_ms), 2),
                    queue_ms=round(float(result.queue_ms), 2),
                    dropped_total=result.dropped_before_start,
                    error=result.error,
                )
                return None
            self._log_result(result)
        return result

    def discard_pending_and_result(self, reason: str = "") -> None:
        with self._condition:
            had_pending = self._pending is not None
            had_result = self._latest_result is not None
            self._discard_before_sequence = max(int(self._discard_before_sequence), int(self._submitted))
            self._pending = None
            self._latest_result = None
        if had_pending or had_result or self._discard_before_sequence:
            event_log(
                "async event observer discarded pending work",
                name=self.name,
                reason=str(reason or ""),
                had_pending=had_pending,
                had_result=had_result,
                discard_before_sequence=self._discard_before_sequence,
                submitted=self._submitted,
                completed=self._completed,
                dropped=self._dropped_pending,
            )

    def stop(self, *, timeout: float = 1.0) -> None:
        with self._condition:
            if self._closed:
                return
            self._closed = True
            self._pending = None
            self._condition.notify_all()
        self._thread.join(timeout=max(0.0, float(timeout)))
        event_log(
            "async event observer stopped",
            name=self.name,
            submitted=self._submitted,
            completed=self._completed,
            dropped=self._dropped_pending,
            throttled=self._throttled_submit,
            alive=self._thread.is_alive(),
        )

    def _run(self) -> None:
        while True:
            with self._condition:
                while self._pending is None and not self._closed:
                    self._condition.wait()
                if self._closed:
                    return
                pending = self._pending
                self._pending = None

            if pending is None:
                continue
            tick, config, submitted_at_ms, submitted_perf, dropped_at_start, sequence = pending
            started_at_ms = int(time.time() * 1000)
            start = time.perf_counter()
            cpu_start = _thread_cpu_time()
            detections = []
            error = ""
            try:
                detections = self.coordinator.monitor.detect(tick, config)
            except Exception as exc:  # noqa: BLE001 - diagnostics should not kill navigation.
                error = f"{exc.__class__.__name__}: {exc}"
            finished_at_ms = int(time.time() * 1000)
            detect_ms = (time.perf_counter() - start) * 1000.0
            detect_cpu_ms = (_thread_cpu_time() - cpu_start) * 1000.0
            queue_ms = max(0.0, (start - submitted_perf) * 1000.0)
            result = AsyncEventDetectionResult(
                tick=tick,
                detections=list(detections or []),
                sequence=int(sequence),
                submitted_at_ms=int(submitted_at_ms),
                started_at_ms=int(started_at_ms),
                finished_at_ms=int(finished_at_ms),
                queue_ms=float(queue_ms),
                detect_ms=float(detect_ms),
                detect_cpu_ms=float(detect_cpu_ms),
                dropped_before_start=int(dropped_at_start),
                error=error,
            )
            with self._condition:
                self._completed += 1
                if int(sequence) <= int(self._discard_before_sequence):
                    should_discard = True
                else:
                    should_discard = False
                    self._latest_result = result
            if should_discard:
                event_log(
                    "async event detection result discarded by reset",
                    name=self.name,
                    seq=int(sequence),
                    discard_before_sequence=int(self._discard_before_sequence),
                    detections=len(result.detections),
                    detect_ms=round(float(result.detect_ms), 2),
                    detect_cpu_ms=round(float(result.detect_cpu_ms), 2),
                )

    def _log_result(self, result: AsyncEventDetectionResult) -> None:
        now_ms = int(time.time() * 1000)
        if not self._should_log_result(result, now_ms):
            return
        shape = getattr(result.tick.raw_minimap_frame, "shape", None)
        frame_shape = "x".join(str(int(value)) for value in shape) if shape is not None else ""
        dropped_since_last = max(0, int(result.dropped_before_start) - int(self._last_logged_dropped))
        event_log(
            "async event detection result",
            name=self.name,
            seq=result.sequence,
            detections=len(result.detections),
            detect_ms=round(float(result.detect_ms), 2),
            detect_cpu_ms=round(float(result.detect_cpu_ms), 2),
            queue_ms=round(float(result.queue_ms), 2),
            total_ms=round(float(result.total_ms), 2),
            result_age_ms=result.age_ms(),
                submitted=self._submitted,
                completed=self._completed,
                dropped_total=result.dropped_before_start,
                throttled=self._throttled_submit,
                dropped_since_last=dropped_since_last,
                frame=frame_shape,
                error=result.error,
        )
        self._last_result_log_ms = int(now_ms)
        self._last_logged_dropped = int(result.dropped_before_start)

    def _should_log_result(self, result: AsyncEventDetectionResult, now_ms: int) -> bool:
        if result.error:
            return True
        if float(result.detect_ms) >= self._slow_detect_ms:
            return True
        if float(result.queue_ms) >= self._slow_queue_ms:
            return True
        if int(result.dropped_before_start) != int(self._last_logged_dropped):
            return True
        return now_ms - int(self._last_result_log_ms) >= int(self._result_log_interval_ms)


def clone_event_tick(tick: EventTick) -> EventTick:
    frame = tick.raw_minimap_frame
    if hasattr(frame, "copy"):
        frame = frame.copy()
    return EventTick(
        now_ms=int(tick.now_ms),
        raw_minimap_frame=frame,
        player_global_pos=_point_or_none(tick.player_global_pos),
        player_local_minimap_pos=_point_or_none(tick.player_local_minimap_pos),
        localization_confidence=float(tick.localization_confidence or 0.0),
        draw_scale=float(tick.draw_scale or 1.0),
        map_name=str(tick.map_name or ""),
        capture_provider=tick.capture_provider,
        frame_registration=copy.copy(tick.frame_registration),
        event_tasks=[],
    )


def snapshot_event_config(config) -> EventSystemConfig:
    if hasattr(config, "to_dict"):
        return EventSystemConfig.from_dict(config.to_dict())
    return EventSystemConfig.from_dict({})


def _observer_interval_ms(config) -> int:
    value = getattr(config, "async_observer_interval_ms", None)
    if value is None:
        raw = getattr(config, "raw", {}) or {}
        value = raw.get("async_observer_interval_ms", 250) if isinstance(raw, dict) else 250
    try:
        return max(0, int(value or 0))
    except (TypeError, ValueError):
        return 250


def _thread_cpu_time() -> float:
    clock = getattr(time, "thread_time", None) or time.process_time
    return float(clock())


def _point_or_none(point) -> tuple[int, int] | None:
    if point is None:
        return None
    try:
        return int(point[0]), int(point[1])
    except (TypeError, ValueError, IndexError):
        return None
