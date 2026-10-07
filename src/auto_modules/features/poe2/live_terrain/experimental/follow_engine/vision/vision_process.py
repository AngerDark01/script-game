"""Spawn-safe latest-only vision process.

The process owns capture and recognition adapters.  It does not import Qt,
game-memory readers, path planners, or controller output adapters.
"""

from __future__ import annotations

import multiprocessing as mp
import queue
import time
import traceback
from dataclasses import dataclass
from typing import Any

from ..contracts import VisualObservation
from .capture_adapter import CapturedFrame, FrameCapture, FrameProcessor


@dataclass(frozen=True, slots=True)
class VisionProcessEvent:
    kind: str
    generation: int
    sequence: int
    observation: VisualObservation | None = None
    error: str = ""
    traceback_text: str = ""
    processing_ms: float = 0.0


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
) -> None:
    last_sequence = -1
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
                elapsed_ms = (time.perf_counter() - started) * 1000.0
                _put_event(
                    output_queue,
                    VisionProcessEvent("observation", generation, last_sequence, observation, processing_ms=elapsed_ms),
                )
            wait_seconds = max(0.001, int(interval_ms) / 1000.0)
            stop_event.wait(wait_seconds)
    except BaseException as exc:  # pragma: no cover - exercised in spawned process
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
    ) -> None:
        if int(interval_ms) < 1:
            raise ValueError("interval_ms must be positive")
        self.capture = capture
        self.processor = processor
        self.interval_ms = int(interval_ms)
        self.context = context or mp.get_context("spawn")
        self.stop_event = self.context.Event()
        self.events = self.context.Queue(maxsize=1)
        self.process = None
        self.generation: int | None = None
        self.map_instance: str | None = None

    def start(self, *, generation: int, map_instance: str) -> None:
        if self.process is not None and self.process.is_alive():
            raise RuntimeError("vision process is already running")
        self.stop_event.clear()
        self.generation = int(generation)
        self.map_instance = str(map_instance).strip()
        if self.generation <= 0 or not self.map_instance:
            raise ValueError("vision process generation/map instance is invalid")
        self.process = self.context.Process(
            target=vision_process_entry,
            args=(self.capture, self.processor, self.events, self.stop_event, self.generation, self.map_instance, self.interval_ms),
            name=f"poe2-follow-vision-{self.generation}",
            daemon=True,
        )
        self.process.start()

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
            return
        process.join(timeout=max(0.0, float(timeout)))
        if process.is_alive():
            process.terminate()
            process.join(timeout=1.0)
        self.process = None
