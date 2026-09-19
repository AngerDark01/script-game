"""PoE2 live localization composition.

This module is deliberately an experiment/business adapter.  Matching policy
is injected through :class:`MapLocalizer`; no input, Host, LAN, or navigation
side effects are owned here.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from time import perf_counter, time
from typing import Any, Callable, Iterable, cast

import cv2
import numpy as np

from auto_modules.core.localization import (
    LocalizationMode,
    LocalizationResult,
    MapLocalizer,
    ObservationCandidate,
    ObservationFrame,
    TrajectoryBuffer,
)
from auto_modules.core.vision import HSVRecognizer

from .calibration import Poe2Calibration
from .player_policy import select_single_player_frame
from .terrain_reference import TerrainReference
from .terrain_reference import build_reference


@dataclass(frozen=True)
class Poe2FrameInput:
    raw_frame: Any
    observation: ObservationFrame
    selected: ObservationCandidate
    captured_at_ms: int


@dataclass(frozen=True)
class Poe2LocalizationState:
    raw_frame: Any = None
    observation: ObservationFrame | None = None
    selected_candidate: ObservationCandidate | None = None
    localization: LocalizationResult = LocalizationResult(None, 0.0, source="failed")
    latest_confirmed_position: tuple[float, float] | None = None
    trajectory: tuple[tuple[float, float], ...] = ()
    mode: str = LocalizationMode.NEED_GLOBAL.value
    source: str = "failed"
    confidence: float = 0.0
    frame_elapsed_ms: float = 0.0
    recognition_elapsed_ms: float = 0.0
    localization_elapsed_ms: float = 0.0
    failure_reason: str = "not_started"

    @property
    def position(self) -> tuple[float, float] | None:
        """The fresh position for this frame, never a center fallback."""
        return self.localization.position

    @property
    def local_position(self) -> tuple[int, int] | None:
        return self.selected_candidate.local_position if self.selected_candidate else None


class Poe2LocalizationRuntime:
    """Compose one PoE2 minimap source into single-player localization state."""

    def __init__(
        self,
        *,
        capture: Any,
        recognize: Callable[[Any, int], ObservationFrame] | Any | None = None,
        localizer: MapLocalizer | None = None,
        global_match: Callable[[Any], Any] | None = None,
        local_match: Callable[[Any, tuple[float, float]], Any] | None = None,
        phase_predict: Callable[[Any, Any], tuple[float, float] | None] | None = None,
        calibration: Poe2Calibration | None = None,
        min_confidence: float = 0.7,
        trajectory: TrajectoryBuffer | None = None,
        logger: Any | None = None,
    ) -> None:
        if capture is None:
            raise ValueError("capture is required")
        if not 0.0 <= float(min_confidence) <= 1.0:
            raise ValueError("min_confidence must be between 0 and 1")
        if localizer is None and (global_match is not None or local_match is not None):
            if not callable(global_match) or not callable(local_match):
                raise TypeError("global_match and local_match must be supplied together")
            localizer = MapLocalizer(
                global_match=global_match,
                local_match=local_match,
                phase_predict=phase_predict,
            )
        self.capture = capture
        self.recognizer = recognize
        self.localizer = localizer
        self.calibration = calibration
        self.reference: TerrainReference | None = None
        self.min_confidence = float(min_confidence)
        self.trajectory = trajectory or TrajectoryBuffer()
        self.logger = logger
        self.active = False
        self._latest_confirmed_position = None
        self._last_state = Poe2LocalizationState()
        self._listeners: list[Callable[[Poe2LocalizationState], None]] = []
        self.search_radius = 96
        self.match_threshold = 0.25

    @property
    def last_state(self) -> Poe2LocalizationState:
        return self._last_state

    @property
    def mode(self) -> LocalizationMode:
        return self.localizer.mode if self.localizer is not None else LocalizationMode.NEED_GLOBAL

    def add_listener(self, listener: Callable[[Poe2LocalizationState], None]) -> None:
        if callable(listener) and listener not in self._listeners:
            self._listeners.append(listener)

    def remove_listener(self, listener: Callable[[Poe2LocalizationState], None]) -> None:
        if listener in self._listeners:
            self._listeners.remove(listener)

    def configure_reference(
        self,
        reference: TerrainReference,
        calibration: Poe2Calibration | None = None,
    ) -> None:
        self.reference = reference
        if calibration is not None:
            self.calibration = calibration
        if self.localizer is not None:
            self.localizer.reset()
        self.trajectory.reset()
        self._latest_confirmed_position = None
        self._log("step=runtime.reference_configured shape=%sx%s", reference.height, reference.width)

    set_reference = configure_reference

    def configure_snapshot(self, snapshot) -> None:
        """Build the localization reference from the captured terrain snapshot."""
        self.configure_reference(build_reference(snapshot))
        if self.localizer is None:
            self.localizer = MapLocalizer(
                global_match=self._global_match,
                local_match=self._local_match,
            )

    def configure_monitor(self, config) -> None:
        self.search_radius = int(getattr(config, "search_radius", self.search_radius))
        self.match_threshold = float(getattr(config, "match_threshold", self.match_threshold))

    def start(self) -> None:
        self.active = True
        if self.localizer is not None and self.mode is LocalizationMode.STOPPED:
            self.localizer.reset()
        self._log("step=runtime.started")

    def stop(self) -> None:
        self.active = False
        if self.localizer is not None:
            self.localizer.stop()
        self.clear_frame()
        self._log("step=runtime.stopped")

    def reset(self) -> None:
        self.active = False
        if self.localizer is not None:
            self.localizer.reset()
        self.trajectory.reset()
        self._latest_confirmed_position = None
        self.clear_frame()
        self._last_state = Poe2LocalizationState()

    def clear_frame(self) -> None:
        self._last_state = replace(self._last_state, raw_frame=None)

    def tick(self, *, now_ms: int | None = None) -> Poe2LocalizationState:
        """Capture and process exactly one frame."""
        started = perf_counter()
        captured_at_ms = int(now_ms if now_ms is not None else time() * 1000)
        try:
            raw_frame = self._capture_frame()
        except Exception as exc:
            return self._failure_state(
                captured_at_ms, started, reason="capture_failed", error=str(exc)
            )
        if raw_frame is None:
            return self._failure_state(captured_at_ms, started, reason="empty_frame")

        recognition_started = perf_counter()
        try:
            observation = self._recognize(raw_frame, captured_at_ms)
            selected_frame = select_single_player_frame(
                observation, min_confidence=self.min_confidence
            )
        except Exception as exc:
            self._log("step=runtime.recognition_failed error=%s", exc)
            return self._failure_state(
                captured_at_ms,
                started,
                reason="recognition_failed",
                raw_frame=raw_frame,
                error=str(exc),
                recognition_elapsed_ms=(perf_counter() - recognition_started) * 1000,
            )
        recognition_elapsed_ms = (perf_counter() - recognition_started) * 1000
        selected = selected_frame.selected
        if selected is None:
            self._log("step=runtime.player_not_detected candidates=%s", len(observation.candidates))
            return self._failure_state(
                captured_at_ms,
                started,
                reason="player_not_detected",
                raw_frame=raw_frame,
                observation=selected_frame,
                recognition_elapsed_ms=recognition_elapsed_ms,
            )
        if self.localizer is None:
            return self._failure_state(
                captured_at_ms,
                started,
                reason="localizer_not_configured",
                raw_frame=raw_frame,
                observation=selected_frame,
                selected=selected,
                recognition_elapsed_ms=recognition_elapsed_ms,
            )

        localization_started = perf_counter()
        frame_input = Poe2FrameInput(raw_frame, selected_frame, selected, captured_at_ms)
        try:
            localization = self.localizer.update(frame_input)
        except Exception as exc:
            self._log("step=runtime.localization_failed error=%s", exc)
            return self._failure_state(
                captured_at_ms,
                started,
                reason="localization_failed",
                raw_frame=raw_frame,
                observation=selected_frame,
                selected=selected,
                recognition_elapsed_ms=recognition_elapsed_ms,
                localization_elapsed_ms=(perf_counter() - localization_started) * 1000,
                error=str(exc),
            )
        localization_elapsed_ms = (perf_counter() - localization_started) * 1000
        if localization.position is not None:
            self._latest_confirmed_position = localization.position
            self.trajectory.append(
                localization.position,
                captured_at_ms=captured_at_ms,
                confidence=localization.confidence,
                fresh=True,
                source=localization.source,
            )
        reason = "" if localization.position is not None else str(
            localization.metadata.get("reason", "localization_failed")
        )
        state = self._state(
            raw_frame=raw_frame,
            observation=selected_frame,
            selected=selected,
            localization=localization,
            captured_at_ms=captured_at_ms,
            started=started,
            recognition_elapsed_ms=recognition_elapsed_ms,
            localization_elapsed_ms=localization_elapsed_ms,
            failure_reason=reason,
        )
        self._publish(state)
        return state

    def _capture_frame(self):
        source = self.capture
        if callable(source):
            return source()
        for name in ("capture", "read", "get_frame"):
            method = getattr(source, name, None)
            if callable(method):
                return method()
        raise TypeError("capture must be callable or expose capture/read/get_frame")

    def _wall_mask(self, raw_frame):
        recognizer = self.recognizer
        source = getattr(recognizer, "recognizer", recognizer)
        method = getattr(source, "extract_walls", None)
        if not callable(method):
            return None
        mask = np.asarray(method(raw_frame))
        if mask.ndim != 2 or mask.size == 0:
            return None
        return np.where(mask > 0, 255, 0).astype(np.uint8)

    def _candidate_delta(self, frame: Poe2FrameInput) -> tuple[float, float]:
        marker = self.calibration.player_local_position if self.calibration else None
        marker = marker or frame.selected.local_position
        return (
            (frame.selected.local_position[0] - marker[0]) * (self.calibration.scale_x if self.calibration else 1.0),
            (frame.selected.local_position[1] - marker[1]) * (self.calibration.scale_y if self.calibration else 1.0),
        )

    def _global_match(self, frame: Poe2FrameInput):
        if self.reference is None:
            return None
        template = self._wall_mask(frame.raw_frame)
        if template is None or int(np.count_nonzero(template)) < 8:
            return None
        target = self.reference.wall_layer
        if template.shape[0] > target.shape[0] or template.shape[1] > target.shape[1]:
            return None
        result = cv2.matchTemplate(target, template, cv2.TM_CCOEFF_NORMED)
        _min, max_value, _min_loc, max_loc = cv2.minMaxLoc(result)
        confidence = max(0.0, min(1.0, float(max_value)))
        if confidence < self.match_threshold:
            return None
        delta_x, delta_y = self._candidate_delta(frame)
        return (
            (float(max_loc[0]) + delta_x, float(max_loc[1]) + delta_y),
            confidence,
        )

    def _local_match(self, frame: Poe2FrameInput, origin: tuple[float, float]):
        if self.reference is None:
            return None
        template = self._wall_mask(frame.raw_frame)
        if template is None or int(np.count_nonzero(template)) < 8:
            return None
        delta_x, delta_y = self._candidate_delta(frame)
        top_left_x = int(round(origin[0] - delta_x))
        top_left_y = int(round(origin[1] - delta_y))
        radius = max(1, int(self.search_radius))
        x0 = max(0, top_left_x - radius)
        y0 = max(0, top_left_y - radius)
        x1 = min(self.reference.width - template.shape[1], top_left_x + radius)
        y1 = min(self.reference.height - template.shape[0], top_left_y + radius)
        if x1 < x0 or y1 < y0:
            return None
        search = self.reference.wall_layer[y0 : y1 + template.shape[0], x0 : x1 + template.shape[1]]
        result = cv2.matchTemplate(search, template, cv2.TM_CCOEFF_NORMED)
        _min, max_value, _min_loc, max_loc = cv2.minMaxLoc(result)
        confidence = max(0.0, min(1.0, float(max_value)))
        if confidence < self.match_threshold:
            return None
        return (
            (float(x0 + max_loc[0]) + delta_x, float(y0 + max_loc[1]) + delta_y),
            confidence,
        )

    def _recognize(self, raw_frame, captured_at_ms: int) -> ObservationFrame:
        recognizer = self.recognizer
        if recognizer is None:
            raise RuntimeError("PoE2 player recognizer is not configured")
        if callable(recognizer):
            value = recognizer(raw_frame, captured_at_ms)
        else:
            method = getattr(recognizer, "detect", None)
            if not callable(method):
                raise TypeError("recognizer must be callable or expose detect")
            value = method(raw_frame)
        if isinstance(value, ObservationFrame):
            return value
        if value is None:
            return ObservationFrame(captured_at_ms=captured_at_ms)
        candidates = list(value) if isinstance(value, (list, tuple)) else [value]
        normalized = []
        for item in candidates:
            item = cast(Any, item)
            if isinstance(item, ObservationCandidate):
                normalized.append(item)
            else:
                position, confidence = item
                normalized.append(ObservationCandidate(tuple(position), float(confidence)))
        return ObservationFrame(captured_at_ms=captured_at_ms, candidates=tuple(normalized), source="poe2")

    def _failure_state(
        self,
        captured_at_ms: int,
        started: float,
        *,
        reason: str,
        raw_frame=None,
        observation=None,
        selected=None,
        recognition_elapsed_ms: float = 0.0,
        localization_elapsed_ms: float = 0.0,
        error: str = "",
    ) -> Poe2LocalizationState:
        metadata = {"reason": reason}
        if error:
            metadata["error"] = error
        localization = LocalizationResult(
            None, 0.0, source="failed", registration_valid=False, metadata=metadata
        )
        state = self._state(
            raw_frame=raw_frame,
            observation=observation,
            selected=selected,
            localization=localization,
            captured_at_ms=captured_at_ms,
            started=started,
            recognition_elapsed_ms=recognition_elapsed_ms,
            localization_elapsed_ms=localization_elapsed_ms,
            failure_reason=reason,
        )
        self._publish(state)
        return state

    def _state(self, *, raw_frame, observation, selected, localization, captured_at_ms, started,
               recognition_elapsed_ms, localization_elapsed_ms, failure_reason):
        mode = self.mode.value if self.localizer is not None else LocalizationMode.NEED_GLOBAL.value
        state = Poe2LocalizationState(
            raw_frame=raw_frame,
            observation=observation,
            selected_candidate=selected,
            localization=localization,
            latest_confirmed_position=self._latest_confirmed_position,
            trajectory=self.trajectory.points,
            mode=mode,
            source=localization.source,
            confidence=float(localization.confidence),
            frame_elapsed_ms=(perf_counter() - started) * 1000,
            recognition_elapsed_ms=recognition_elapsed_ms,
            localization_elapsed_ms=localization_elapsed_ms,
            failure_reason=failure_reason,
        )
        return state

    def _publish(self, state: Poe2LocalizationState) -> None:
        self._last_state = state
        for listener in tuple(self._listeners):
            try:
                listener(state)
            except Exception:
                self._log("step=runtime.listener_failed")

    def _log(self, message: str, *args) -> None:
        if self.logger is not None:
            self.logger.info(message, *args)


# Friendly alias for callers that name the business boundary explicitly.
LocalizationRuntime = Poe2LocalizationRuntime


class HSVPlayerObservationRecognizer:
    """Adapt the reusable HSV player mask into generic candidates."""

    def __init__(self, recognizer: HSVRecognizer | None = None, *, min_area: float = 3.0) -> None:
        self.recognizer = recognizer or HSVRecognizer()
        self.min_area = float(min_area)

    def __call__(self, frame, captured_at_ms: int) -> ObservationFrame:
        mask = np.asarray(self.recognizer.extract_player(frame))
        candidates: list[ObservationCandidate] = []
        if mask.ndim == 2 and mask.size:
            contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            for contour in contours:
                area = float(cv2.contourArea(contour))
                if area < self.min_area:
                    continue
                moments = cv2.moments(contour)
                if moments["m00"] == 0:
                    continue
                center = (
                    int(round(moments["m10"] / moments["m00"])),
                    int(round(moments["m01"] / moments["m00"])),
                )
                confidence = min(0.99, 0.55 + min(area, 45.0) / 100.0)
                candidates.append(
                    ObservationCandidate(
                        center,
                        confidence,
                        identity_hint="poe2-player-candidate",
                        evidence={"area": area},
                    )
                )
        candidates.sort(key=lambda item: item.confidence, reverse=True)
        return ObservationFrame(
            captured_at_ms=int(captured_at_ms),
            candidates=tuple(candidates),
            source="hsv-player-mask",
        )

__all__ = [
    "LocalizationRuntime",
    "Poe2FrameInput",
    "Poe2LocalizationRuntime",
    "Poe2LocalizationState",
    "HSVPlayerObservationRecognizer",
]
