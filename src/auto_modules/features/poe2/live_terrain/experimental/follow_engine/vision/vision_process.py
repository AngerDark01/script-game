"""Spawn-safe latest-only vision process.

The process owns capture and recognition adapters.  It does not import Qt,
game-memory readers, path planners, or controller output adapters.
"""

from __future__ import annotations

import multiprocessing as mp
import queue
import logging
import time
import traceback
from dataclasses import dataclass
from typing import Any

from ..contracts import VisualObservation
from ..shared_frame_ring import SharedFrameRecord, SharedFrameRing
from ..worker_lifecycle import stop_process, close_queues
from .capture_adapter import CapturedFrame, FrameCapture, FrameProcessor
from ..diagnostic_events import DiagnosticJournal
from dataclasses import asdict


_LOGGER = logging.getLogger("auto_modules.poe2_live_terrain.follow_engine")


def _cadence_wait_seconds(*, started: float, interval_ms: int, now: float | None = None) -> float:
    """Return the remaining wait for a fixed capture cadence.

    ``interval_ms`` is the start-to-start period.  Waiting for the full period
    after processing would silently halve the requested FPS whenever vision
    work takes a substantial fraction of the period.  A tiny yield remains
    when the worker is already late so a hot capture backend cannot spin.
    """
    current = time.perf_counter() if now is None else float(now)
    remaining = float(started) + max(1, int(interval_ms)) / 1000.0 - current
    return max(0.001, remaining)


@dataclass(frozen=True, slots=True)
class VisionProcessEvent:
    kind: str
    generation: int
    sequence: int
    observation: VisualObservation | None = None
    frame: CapturedFrame | None = None
    error: str = ""
    traceback_text: str = ""
    processing_ms: float = 0.0
    frame_in_ring: bool = False
    diagnostic_events: tuple = ()


def _put_event(output_queue, event: VisionProcessEvent) -> None:
    """Keep event transport bounded; a newer observation supersedes an old one."""
    try:
        while True:
            output_queue.get_nowait()
    except queue.Empty:
        pass
    try:
        output_queue.put_nowait(event)
    except queue.Full:
        pass


def vision_process_entry(
    capture: FrameCapture,
    processor: FrameProcessor,
    output_queue,
    stop_event,
    generation: int,
    map_instance: str,
    interval_ms: int,
    frame_ring: SharedFrameRing | None = None,
) -> None:
    last_sequence = -1
    terminal_error = False
    journal = DiagnosticJournal()
    try:
        while not stop_event.is_set():
            started = time.perf_counter()
            frame = capture.capture()
            if frame is not None:
                if not isinstance(frame, CapturedFrame):
                    raise TypeError("capture adapter must return CapturedFrame or None")
                if int(frame.generation) != int(generation) or str(frame.map_instance).strip() != str(map_instance).strip():
                    raise ValueError("capture frame belongs to a different generation or map instance")
                if int(frame.sequence) <= last_sequence:
                    # A stale frame is harmless; discard it without publishing
                    # an error that could make the control process recover.
                    # Keep the capture cadence bounded even when a provider
                    # accidentally repeats a sequence forever.
                    stop_event.wait(
                        _cadence_wait_seconds(started=started, interval_ms=interval_ms)
                    )
                    continue
                last_sequence = int(frame.sequence)
                observation = processor.process(frame)
                if not isinstance(observation, VisualObservation):
                    raise TypeError("frame processor must return VisualObservation")
                if (
                    observation.generation != generation
                    or observation.sequence != frame.sequence
                    or observation.map_instance != map_instance
                ):
                    raise ValueError("visual observation header does not match captured frame")
                frame_in_ring = False
                event_frame: CapturedFrame | None = frame
                if frame_ring is not None:
                    published = frame_ring.publish(
                        SharedFrameRecord(
                            generation=frame.generation,
                            sequence=frame.sequence,
                            captured_at_ms=frame.captured_at_ms,
                            map_instance=frame.map_instance,
                            payload=frame.payload,
                        )
                    )
                    frame_in_ring = bool(published)
                    if frame_in_ring:
                        # Only the small observation header crosses the queue;
                        # the control process reads the encoded bytes from the
                        # shared ring when a local recovery needs them.
                        event_frame = None
                elapsed_ms = (time.perf_counter() - started) * 1000.0
                association = dict(observation.association_diagnostics)
                reason = (
                    "single_confirmed" if association.get("single_candidate_confirmed") else
                    "single_pending" if association.get("single_candidate_pending") else
                    "area_filtered" if association.get("filtered_large_area_ids") else
                    str(observation.source)
                )
                journal.record("vision", "all", reason,
                    sequence=last_sequence, captured_at_ms=frame.captured_at_ms,
                    map_instance=map_instance, association=association,
                    wall_quality=observation.wall_quality, wall_shift=observation.wall_shift,
                    timing=asdict(observation.timing), processing_ms=elapsed_ms)
                _put_event(
                    output_queue,
                    VisionProcessEvent(
                        "observation",
                        generation,
                        last_sequence,
                        observation,
                        frame=event_frame,
                        frame_in_ring=frame_in_ring,
                        processing_ms=elapsed_ms,
                        diagnostic_events=journal.snapshot(),
                    ),
                )
                if last_sequence == 0 or last_sequence % 30 == 0:
                    _LOGGER.info(
                        "step=follow_engine.vision_child_progress generation=%s sequence=%s "
                        "processing_ms=%.1f frame_in_ring=%s pid=%s source=%s "
                        "assignment_score=%.3f association=%s",
                        generation, last_sequence, elapsed_ms, frame_in_ring,
                        mp.current_process().pid, observation.source,
                        float(observation.assignment_score),
                        dict(observation.association_diagnostics),
                    )
            stop_event.wait(
                _cadence_wait_seconds(started=started, interval_ms=interval_ms)
            )
    except BaseException as exc:  # pragma: no cover - exercised in spawned process
        terminal_error = True
        _put_event(
            output_queue,
            VisionProcessEvent(
                "error",
                int(generation),
                last_sequence,
                error=f"{type(exc).__name__}: {exc}",
                traceback_text=traceback.format_exc(),
            ),
        )
    finally:
        for resource in (processor, capture):
            close = getattr(resource, "close", None)
            if callable(close):
                try:
                    close()
                except Exception:
                    pass
        if frame_ring is not None:
            try:
                frame_ring.close()
            except Exception:
                pass
        # Do not let the latest-only stopped marker erase the structured
        # error.  The parent needs the traceback to distinguish a processor
        # failure from an intentional stop; it may still observe process exit
        # through ``is_alive``/supervisor state.
        if not terminal_error:
            _put_event(output_queue, VisionProcessEvent("stopped", int(generation), last_sequence))


class VisionProcessHandle:
    """Parent-side lifecycle wrapper with explicit stop and bounded polling."""

    def __init__(
        self,
        capture: FrameCapture,
        processor: FrameProcessor,
        *,
        interval_ms: int = 33,
        context: mp.context.BaseContext | None = None,
        frame_ring: SharedFrameRing | None = None,
    ) -> None:
        if int(interval_ms) < 1:
            raise ValueError("interval_ms must be positive")
        self.capture = capture
        self.processor = processor
        self.interval_ms = int(interval_ms)
        self.context = context or mp.get_context("spawn")
        self.frame_ring = frame_ring
        self.stop_event = self.context.Event()
        self.events = self.context.Queue(maxsize=1)
        self.process = None
        self.generation: int | None = None
        self.map_instance: str | None = None

    def start(self, *, generation: int, map_instance: str) -> None:
        if self.process is not None and self.process.is_alive():
            raise RuntimeError("vision process is already running")
        while True:
            try:
                self.events.get_nowait()
            except queue.Empty:
                break
        self.stop_event.clear()
        self.generation = int(generation)
        self.map_instance = str(map_instance).strip()
        if self.generation <= 0 or not self.map_instance:
            raise ValueError("vision process generation/map instance is invalid")
        if self.frame_ring is not None:
            self.frame_ring.rebind_session(map_instance=self.map_instance)
        for resource in (self.capture, self.processor):
            rebind = getattr(resource, "rebind_session", None)
            if callable(rebind):
                rebind(generation=self.generation, map_instance=self.map_instance)
        self.process = self.context.Process(
            target=vision_process_entry,
            args=(
                self.capture,
                self.processor,
                self.events,
                self.stop_event,
                self.generation,
                self.map_instance,
                self.interval_ms,
                self.frame_ring,
            ),
            name=f"poe2-follow-vision-{self.generation}",
            daemon=True,
        )
        _LOGGER.info(
            "step=follow_engine.vision_start handle_id=%s queue_id=%s generation=%s instance=%s",
            id(self), id(self.events), generation, map_instance,
        )
        self.process.start()
        _LOGGER.info(
            "step=follow_engine.vision_process_started handle_id=%s pid=%s alive=%s generation=%s",
            id(self), getattr(self.process, "pid", None), self.process.is_alive(), generation,
        )

    def poll_latest(self) -> VisionProcessEvent | None:
        latest = None
        while True:
            try:
                latest = self.events.get_nowait()
            except queue.Empty:
                return latest

    def stop(self, *, timeout: float = 2.0) -> None:
        self.stop_event.set()
        process = self.process
        if process is None:
            _LOGGER.info("step=follow_engine.vision_process_stop_skipped handle_id=%s reason=not_started", id(self))
            return
        process_pid = getattr(process, "pid", None)
        _LOGGER.info(
            "step=follow_engine.vision_process_stop_requested handle_id=%s pid=%s alive=%s timeout_s=%.2f",
            id(self), process_pid, process.is_alive(), timeout,
        )
        forced = stop_process(process, timeout=timeout)
        if forced and self.frame_ring is not None:
            self.frame_ring.invalidate()
        self.process = None
        _LOGGER.info(
            "step=follow_engine.vision_process_stopped handle_id=%s pid=%s forced=%s alive=False",
            id(self), process_pid, forced,
        )

    def dispose(self) -> None:
        _LOGGER.info(
            "step=follow_engine.vision_dispose handle_id=%s queue_id=%s generation=%s instance=%s",
            id(self), id(self.events), self.generation, self.map_instance,
        )
        self.stop()
        close_queues(self.events)
        _LOGGER.info("step=follow_engine.vision_queue_closed handle_id=%s queue_id=%s", id(self), id(self.events))
