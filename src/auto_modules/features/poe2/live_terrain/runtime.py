"""PoE2 live localization composition.

This module is deliberately an experiment/business adapter.  Matching policy
is injected through :class:`MapLocalizer`; no input, Host, LAN, or navigation
side effects are owned here.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
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
class Poe2VisualEvidence:
    """Mapping-compatible visual layers produced for one minimap frame."""

    processed_frame: Any = None
    match_mask: Any = None
    wall_mask: Any = None
    fog_mask: Any = None


@dataclass(frozen=True)
class Poe2FrameInput:
    raw_frame: Any
    observation: ObservationFrame
    selected: ObservationCandidate
    captured_at_ms: int
    visual: Poe2VisualEvidence | None = None


@dataclass(frozen=True)
class Poe2LocalizationState:
    raw_frame: Any = None
    processed_frame: Any = None
    match_mask: Any = None
    wall_mask: Any = None
    fog_mask: Any = None
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
    recognition_diagnostics: dict[str, Any] = field(default_factory=dict)

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
        # PoE2's minimap marker is intentionally small after capture scaling;
        # the recognizer still rejects tiny components and the single-player
        # policy fails closed on ambiguity.
        min_confidence: float = 0.6,
        trajectory: TrajectoryBuffer | None = None,
        logger: Any | None = None,
        preview_capture: Callable[[Any], Any] | None = None,
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
        recognizer_source = getattr(recognize, "recognizer", recognize)
        get_params = getattr(recognizer_source, "get_params", None)
        initial_params = get_params() if callable(get_params) else None
        self._default_recognizer_params = (
            dict(initial_params) if isinstance(initial_params, dict) else {}
        )
        self.localizer = localizer
        self.calibration = calibration
        self.reference: TerrainReference | None = None
        self._snapshot = None
        self.min_confidence = float(min_confidence)
        self.trajectory = trajectory or TrajectoryBuffer()
        self.logger = logger
        self.preview_capture = preview_capture
        self.active = False
        self._latest_confirmed_position = None
        self._last_state = Poe2LocalizationState()
        self._listeners: list[Callable[[Poe2LocalizationState], None]] = []
        self.search_radius = 96
        self.match_threshold = 0.25
        self.selection_mode = "region"
        self.center_position: tuple[int, int] | None = None

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
        self._snapshot = None
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
        self._snapshot = snapshot
        self._configure_snapshot_reference()
        if self.localizer is None:
            self.localizer = MapLocalizer(
                global_match=self._global_match,
                local_match=self._local_match,
            )

    def _configure_snapshot_reference(self) -> None:
        if self._snapshot is None:
            return
        reference = build_reference(self._snapshot)
        self.reference = reference
        if self.localizer is not None:
            self.localizer.reset()
        self.trajectory.reset()
        self._latest_confirmed_position = None
        self._log(
            "step=runtime.reference_configured shape=%sx%s coordinate_space=native",
            reference.height,
            reference.width,
        )

    def configure_monitor(self, config) -> None:
        self.search_radius = int(getattr(config, "search_radius", self.search_radius))
        self.match_threshold = float(getattr(config, "match_threshold", self.match_threshold))
        self.selection_mode = str(getattr(config, "selection_mode", "region")).strip().lower()
        binding = getattr(config, "binding", None)
        marker = getattr(binding, "player_marker_position", None) if binding is not None else None
        if marker is not None:
            self.center_position = (int(marker[0]), int(marker[1]))
        else:
            self.center_position = None
        params = getattr(config, "recognizer_params", None) or self._default_recognizer_params
        source = getattr(self.recognizer, "recognizer", self.recognizer)
        set_params = getattr(source, "set_params", None)
        if callable(set_params):
            set_params(dict(params))
        self._log("step=runtime.monitor_configured coordinate_space=native")

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
        self._last_state = replace(
            self._last_state,
            raw_frame=None,
            processed_frame=None,
            match_mask=None,
            wall_mask=None,
            fog_mask=None,
        )

    def capture_preview(self, config=None):
        """Capture one calibration frame, including an unsaved editor config."""
        if self.preview_capture is not None:
            return self.preview_capture(config)
        return self._capture_frame()

    def get_recognizer_params(self) -> dict[str, Any]:
        source = getattr(self.recognizer, "recognizer", self.recognizer)
        get_params = getattr(source, "get_params", None)
        value = get_params() if callable(get_params) else None
        return dict(value) if isinstance(value, dict) else {}

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
            observation = self._recognize_or_use_center(raw_frame, captured_at_ms)
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
        recognition_diagnostics = self._recognition_diagnostics(observation)
        selected = selected_frame.selected
        try:
            visual = self._build_visual_evidence(
                raw_frame,
                selected.local_position if selected is not None else None,
            )
        except Exception as exc:
            self._log("step=runtime.visual_processing_failed error=%s", exc)
            return self._failure_state(
                captured_at_ms,
                started,
                reason="visual_processing_failed",
                raw_frame=raw_frame,
                observation=selected_frame,
                selected=selected,
                recognition_elapsed_ms=recognition_elapsed_ms,
                error=str(exc),
                recognition_diagnostics=recognition_diagnostics,
            )
        if selected is None:
            self._log(
                "step=runtime.player_not_detected candidates=%s accepted=%s reason=%s "
                "max_confidence=%.3f mask_pixels=%s hsv=%s-%s candidate_positions=%s "
                "contour_areas=%s",
                recognition_diagnostics["candidate_count"],
                recognition_diagnostics["accepted_count"],
                recognition_diagnostics["reason"],
                recognition_diagnostics["max_confidence"],
                recognition_diagnostics.get("mask_pixels", "-"),
                recognition_diagnostics.get("hsv_min", "-"),
                recognition_diagnostics.get("hsv_max", "-"),
                recognition_diagnostics.get("candidate_positions", []),
                recognition_diagnostics.get("contour_areas", []),
            )
            return self._failure_state(
                captured_at_ms,
                started,
                reason="player_not_detected",
                raw_frame=raw_frame,
                observation=selected_frame,
                recognition_elapsed_ms=recognition_elapsed_ms,
                recognition_diagnostics=recognition_diagnostics,
                visual=visual,
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
                recognition_diagnostics=recognition_diagnostics,
                visual=visual,
            )

        localization_started = perf_counter()
        frame_input = Poe2FrameInput(
            raw_frame,
            selected_frame,
            selected,
            captured_at_ms,
            visual=visual,
        )
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
                recognition_diagnostics=recognition_diagnostics,
                visual=visual,
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
            recognition_diagnostics=recognition_diagnostics,
            visual=visual,
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

    def _build_visual_evidence(
        self,
        raw_frame,
        player_position: tuple[int, int] | None,
    ) -> Poe2VisualEvidence:
        source = getattr(self.recognizer, "recognizer", self.recognizer)
        preprocess = getattr(source, "preprocess_image", None)
        extract_combined = getattr(source, "extract_combined", None)
        processed = preprocess(raw_frame) if callable(preprocess) else raw_frame
        if not callable(extract_combined):
            wall_mask = self._wall_mask(raw_frame)
            return Poe2VisualEvidence(
                processed_frame=processed,
                match_mask=wall_mask,
                wall_mask=wall_mask,
            )
        match_mask, wall_mask, fog_mask = cast(
            tuple[Any, Any, Any],
            extract_combined(raw_frame, player_pos=player_position),
        )
        return Poe2VisualEvidence(
            processed_frame=processed,
            match_mask=self._normalize_mask(match_mask),
            wall_mask=self._normalize_mask(wall_mask),
            fog_mask=self._normalize_mask(fog_mask),
        )

    @staticmethod
    def _normalize_mask(mask):
        if mask is None:
            return None
        array = np.asarray(mask)
        if array.ndim != 2 or array.size == 0:
            return None
        if array.dtype == np.bool_:
            return array.astype(np.uint8) * 255
        return np.clip(array, 0, 255).astype(np.uint8)

    @staticmethod
    def _match_mask(frame: Poe2FrameInput):
        visual = getattr(frame, "visual", None)
        return getattr(visual, "match_mask", None) if visual is not None else None

    def _candidate_delta(self, frame: Poe2FrameInput) -> tuple[float, float]:
        marker = self.calibration.player_local_position if self.calibration else None
        marker = marker or frame.selected.local_position
        delta = (
            (frame.selected.local_position[0] - marker[0]) * (self.calibration.scale_x if self.calibration else 1.0),
            (frame.selected.local_position[1] - marker[1]) * (self.calibration.scale_y if self.calibration else 1.0),
        )
        return delta

    def _global_match(self, frame: Poe2FrameInput):
        if self.reference is None:
            return None
        template = self._match_mask(frame)
        if template is None:
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
        template = self._match_mask(frame)
        if template is None:
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

    def _recognize_or_use_center(self, raw_frame, captured_at_ms: int) -> ObservationFrame:
        """Resolve the configured single-player center without image recognition.

        Center mode is a deliberate geometric contract: the selected center is
        the player's local minimap coordinate, so HSV/shape recognition must
        not be called. Region mode keeps the multi-candidate recognition path.
        """
        if self.selection_mode != "center":
            return self._recognize(raw_frame, captured_at_ms)

        marker = self.center_position
        if marker is None:
            array = np.asarray(raw_frame)
            if array.ndim < 2 or array.shape[0] <= 0 or array.shape[1] <= 0:
                raise ValueError("center mode requires a non-empty captured frame")
            marker = (int(array.shape[1] // 2), int(array.shape[0] // 2))
        array = np.asarray(raw_frame)
        if array.ndim >= 2:
            width, height = int(array.shape[1]), int(array.shape[0])
            marker = (
                max(0, min(int(marker[0]), width - 1)),
                max(0, min(int(marker[1]), height - 1)),
            )
        recognizer = cast(Any, self.recognizer)
        if hasattr(recognizer, "last_diagnostics"):
            recognizer.last_diagnostics = {
                "mode": "center",
                "reason": "center_configured",
                "candidate_count": 1,
                "candidate_positions": [list(marker)],
                "mask_pixels": "not_used",
            }
        return ObservationFrame(
            captured_at_ms=int(captured_at_ms),
            candidates=(
                ObservationCandidate(
                    marker,
                    1.0,
                    identity_hint="poe2-configured-center",
                    evidence={"mode": "center"},
                ),
            ),
            selected_index=0,
            source="configured-center",
        )

    def _recognition_diagnostics(self, observation: ObservationFrame) -> dict[str, Any]:
        """Normalize recognizer diagnostics and add the policy decision."""
        diagnostics = dict(getattr(self.recognizer, "last_diagnostics", {}) or {})
        candidates = tuple(observation.candidates)
        confidences = [float(candidate.confidence) for candidate in candidates]
        accepted_count = sum(confidence >= self.min_confidence for confidence in confidences)
        diagnostics.update(
            {
                "candidate_count": len(candidates),
                "accepted_count": accepted_count,
                "max_confidence": max(confidences, default=0.0),
                "confidence_threshold": self.min_confidence,
            }
        )
        if self.selection_mode == "center" or diagnostics.get("mode") == "center":
            diagnostics["mode"] = "center"
            diagnostics["reason"] = "center_configured"
        elif not candidates:
            diagnostics["reason"] = diagnostics.get("reason", "no_contour")
        elif accepted_count == 0:
            diagnostics["reason"] = "below_confidence"
        elif accepted_count > 1:
            diagnostics["reason"] = "ambiguous"
        else:
            diagnostics["reason"] = "ready"
        return diagnostics

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
        recognition_diagnostics: dict[str, Any] | None = None,
        visual: Poe2VisualEvidence | None = None,
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
            recognition_diagnostics=recognition_diagnostics or {},
            visual=visual,
        )
        self._publish(state)
        return state

    def _state(
        self,
        *,
        raw_frame,
        observation,
        selected,
        localization,
        captured_at_ms,
        started,
        recognition_elapsed_ms,
        localization_elapsed_ms,
        failure_reason,
        recognition_diagnostics=None,
        visual: Poe2VisualEvidence | None = None,
    ):
        mode = self.mode.value if self.localizer is not None else LocalizationMode.NEED_GLOBAL.value
        state = Poe2LocalizationState(
            raw_frame=raw_frame,
            processed_frame=visual.processed_frame if visual is not None else None,
            match_mask=visual.match_mask if visual is not None else None,
            wall_mask=visual.wall_mask if visual is not None else None,
            fog_mask=visual.fog_mask if visual is not None else None,
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
            recognition_diagnostics=dict(recognition_diagnostics or {}),
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
        self.last_diagnostics: dict[str, Any] = {}

    def __call__(self, frame, captured_at_ms: int) -> ObservationFrame:
        mask = np.asarray(self.recognizer.extract_player(frame))
        candidates: list[ObservationCandidate] = []
        contour_areas: list[float] = []
        filtered_by_min_area = 0
        zero_moment = 0
        self.last_diagnostics = {
            "hsv_min": np.asarray(self.recognizer.player_hsv_min).astype(int).tolist(),
            "hsv_max": np.asarray(self.recognizer.player_hsv_max).astype(int).tolist(),
            "min_area": self.min_area,
            "mask_shape": tuple(int(value) for value in mask.shape),
            "mask_pixels": int(np.count_nonzero(mask)) if mask.size else 0,
        }
        if mask.ndim == 2 and mask.size:
            contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            self.last_diagnostics["contour_count"] = len(contours)
            for contour in contours:
                area = float(cv2.contourArea(contour))
                contour_areas.append(area)
                if area < self.min_area:
                    filtered_by_min_area += 1
                    continue
                moments = cv2.moments(contour)
                if moments["m00"] == 0:
                    zero_moment += 1
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
        else:
            self.last_diagnostics["contour_count"] = 0
        self.last_diagnostics.update(
            {
                "contour_areas": contour_areas,
                "filtered_by_min_area": filtered_by_min_area,
                "zero_moment": zero_moment,
                "candidate_confidences": [float(item.confidence) for item in candidates],
                "candidate_positions": [list(item.local_position) for item in candidates],
                "max_area": max(contour_areas, default=0.0),
                "reason": (
                    "candidates_ready"
                    if candidates
                    else "no_contour"
                    if not contour_areas
                    else "below_min_area"
                ),
            }
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
    "Poe2VisualEvidence",
    "HSVPlayerObservationRecognizer",
]
