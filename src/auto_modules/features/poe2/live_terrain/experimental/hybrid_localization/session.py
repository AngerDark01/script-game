"""Timer-agnostic session for the PoE2 hybrid-localization experiment."""

from __future__ import annotations

import time
from time import perf_counter
from typing import Any, Callable

from .models import HybridFrame, HybridLocalizationState


class Poe2HybridLocalizationSession:
    def __init__(
        self,
        *,
        frame_source: Any,
        evidence_builder: Any,
        config_provider: Callable[[], Any],
        controller: Any,
        clock_ms: Callable[[], int] | None = None,
    ) -> None:
        self.frame_source = frame_source
        self.evidence_builder = evidence_builder
        self.config_provider = config_provider
        self.controller = controller
        self.clock_ms = clock_ms or (lambda: int(time.time() * 1000))
        self.active = False
        self._frame_id = 0
        self._listeners: list[Callable[[HybridLocalizationState], None]] = []
        self.last_raw_frame: Any | None = None
        self.last_evidence: Any | None = None
        self.last_frame: HybridFrame | None = None
        self.last_timing_ms: dict[str, float] = {}

    def add_listener(self, listener: Callable[[HybridLocalizationState], None]) -> None:
        if callable(listener) and listener not in self._listeners:
            self._listeners.append(listener)

    def remove_listener(self, listener: Callable[[HybridLocalizationState], None]) -> None:
        if listener in self._listeners:
            self._listeners.remove(listener)

    def start(self) -> None:
        self.controller.start()
        self.active = True

    def stop(self) -> None:
        self.active = False
        self.controller.stop()

    def reset(self) -> None:
        self.active = False
        self._frame_id = 0
        self.last_raw_frame = None
        self.last_evidence = None
        self.last_frame = None
        self.controller.reset()

    def retry_recovery(self) -> None:
        self.controller.retry_recovery()

    def tick(self, *, now_ms: int | None = None) -> HybridLocalizationState:
        if not self.active:
            raise RuntimeError("hybrid localization session is not running")
        prepared = self.controller.prepare_capture()
        if prepared is not None:
            self._publish(prepared)
            return prepared
        config = self.config_provider()
        capture_started = perf_counter()
        raw = self.frame_source.capture(config)
        capture_ended = perf_counter()
        stamp = int(self.clock_ms() if now_ms is None else now_ms)
        evidence = self.evidence_builder.build(raw, config)
        evidence_ended = perf_counter()
        self._frame_id += 1
        frame = HybridFrame.from_evidence(
            evidence,
            captured_at_ms=stamp,
            frame_id=self._frame_id,
        )
        self.last_raw_frame = raw
        self.last_evidence = evidence
        self.last_frame = frame
        state = self.controller.update(frame)
        localization_ended = perf_counter()
        self.last_timing_ms = {
            "capture_ms": (capture_ended - capture_started) * 1000.0,
            "evidence_ms": (evidence_ended - capture_ended) * 1000.0,
            "localization_ms": (localization_ended - evidence_ended) * 1000.0,
        }
        self._publish(state)
        return state

    def _publish(self, state: HybridLocalizationState) -> None:
        for listener in tuple(self._listeners):
            listener(state)


__all__ = ["Poe2HybridLocalizationSession"]
