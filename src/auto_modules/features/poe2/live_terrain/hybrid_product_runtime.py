"""Product-facing runtime adapter for PoE2 hybrid localization."""

from __future__ import annotations

from dataclasses import dataclass, field
from time import perf_counter
from types import MappingProxyType
from typing import Any, Callable, Mapping


@dataclass(frozen=True)
class Poe2HybridProductState:
    """Hybrid state plus visual evidence consumed by the formal UI."""

    mode: Any
    position: tuple[float, float] | None
    latest_confirmed_position: tuple[float, float] | None
    trajectory: tuple[tuple[float, float], ...]
    registration: Any
    source: str
    confidence: float
    reason: str
    recovery_revision: int
    memory_read_count: int
    diagnostics: Mapping[str, Any] = field(default_factory=dict)
    raw_frame: Any = None
    processed_frame: Any = None
    match_mask: Any = None
    local_position: tuple[float, float] | None = None
    frame_elapsed_ms: float = 0.0

    def __post_init__(self) -> None:
        object.__setattr__(self, "diagnostics", MappingProxyType(dict(self.diagnostics)))

    @property
    def failure_reason(self) -> str:
        return self.reason

    @property
    def recognition_diagnostics(self) -> Mapping[str, Any]:
        return self.diagnostics


class Poe2HybridProductRuntime:
    """Own one hybrid experiment while leaving scheduling to the UI."""

    run_in_background = True

    def __init__(
        self,
        experiment_factory: Callable[[Any, Callable[[], Any]], Any],
        *,
        initial_config: Any,
        logger: Any | None = None,
        failure_recorder: Any | None = None,
        performance_log_every: int = 30,
    ) -> None:
        if not callable(experiment_factory):
            raise TypeError("experiment_factory must be callable")
        self._factory = experiment_factory
        self._config = initial_config
        self._logger = logger
        self._failure_recorder = failure_recorder
        self._performance_log_every = max(1, int(performance_log_every))
        self._snapshot: Any | None = None
        self._experiment: Any | None = None
        self._last_state_signature: tuple[Any, ...] | None = None
        self._recorded_failures: set[tuple[int, str]] = set()
        self._tick_count = 0
        self._elapsed_total_ms = 0.0
        self._elapsed_max_ms = 0.0
        self._performance_window_started = perf_counter()
        self._segment_totals: dict[str, float] = {}
        self.active = False

    @property
    def experiment(self) -> Any | None:
        return self._experiment

    def configure_monitor(self, config: Any) -> None:
        self._config = config

    def configure_snapshot(self, snapshot: Any) -> None:
        if snapshot is None:
            raise ValueError("snapshot is required")
        self.stop()
        self._snapshot = snapshot
        self._experiment = self._factory(snapshot, lambda: self._config)
        self._last_state_signature = None
        self._recorded_failures.clear()
        self._reset_performance_window()
        self._log("step=product_localization.configured")

    def start(self) -> None:
        experiment = self._require_experiment()
        experiment.session.start()
        self.active = True
        self._log("step=product_localization.started")

    def stop(self) -> None:
        if self._experiment is not None:
            self._experiment.session.stop()
        self.active = False
        self._log("step=product_localization.stopped")

    def tick(self, *, now_ms: int | None = None) -> Poe2HybridProductState:
        experiment = self._require_experiment()
        started = perf_counter()
        state = experiment.session.tick(now_ms=now_ms)
        elapsed_ms = (perf_counter() - started) * 1000.0
        result = self._adapt_state(experiment, state, elapsed_ms=elapsed_ms)
        self._observe_state(experiment, result)
        return result

    def retry_recovery(self) -> None:
        experiment = self._require_experiment()
        experiment.session.retry_recovery()
        self._log("step=product_localization.retry_requested")

    def _require_experiment(self) -> Any:
        if self._experiment is None:
            raise RuntimeError("请先获取当前地图")
        return self._experiment

    @staticmethod
    def _adapt_state(experiment: Any, state: Any, *, elapsed_ms: float) -> Poe2HybridProductState:
        session = experiment.session
        evidence = getattr(session, "last_evidence", None)
        frame = getattr(session, "last_frame", None)
        processed = getattr(evidence, "processed", None)
        match_mask = getattr(evidence, "wall_mask", None)
        if match_mask is None:
            match_mask = getattr(evidence, "feature", None)
        provider = getattr(experiment, "anchor_provider", None)
        return Poe2HybridProductState(
            mode=getattr(state, "mode", "unknown"),
            position=getattr(state, "position", None),
            latest_confirmed_position=getattr(state, "latest_confirmed_position", None),
            trajectory=tuple(getattr(state, "trajectory", ()) or ()),
            registration=getattr(state, "registration", None),
            source=str(getattr(state, "source", "failed")),
            confidence=float(getattr(state, "confidence", 0.0)),
            reason=str(getattr(state, "reason", "") or ""),
            recovery_revision=int(getattr(state, "recovery_revision", 0)),
            memory_read_count=int(getattr(provider, "read_count", 0)),
            diagnostics={
                **dict(getattr(state, "diagnostics", {}) or {}),
                **dict(getattr(session, "last_timing_ms", {}) or {}),
            },
            raw_frame=getattr(session, "last_raw_frame", None),
            processed_frame=processed,
            match_mask=match_mask,
            local_position=getattr(frame, "local_player", None),
            frame_elapsed_ms=elapsed_ms,
        )

    def _log(self, message: str, *args: Any) -> None:
        if self._logger is not None:
            self._logger.info(message, *args)

    def _observe_state(self, experiment: Any, state: Poe2HybridProductState) -> None:
        mode = getattr(state.mode, "value", state.mode)
        signature = (
            mode,
            state.source,
            state.reason,
            state.recovery_revision,
            state.memory_read_count,
        )
        if signature != self._last_state_signature:
            log = getattr(
                self._logger,
                "warning" if state.reason else "info",
                None,
            )
            if callable(log):
                log(
                    "step=product_localization.state_changed mode=%s source=%s "
                    "confidence=%.3f position=%s latest=%s local=%s "
                    "trajectory_len=%s recovery_revision=%s read_count=%s "
                    "elapsed_ms=%.1f reason=%s diagnostics=%s",
                    mode,
                    state.source,
                    state.confidence,
                    state.position,
                    state.latest_confirmed_position,
                    state.local_position,
                    len(state.trajectory),
                    state.recovery_revision,
                    state.memory_read_count,
                    state.frame_elapsed_ms,
                    state.reason,
                    dict(state.diagnostics),
                )
            self._last_state_signature = signature
        self._record_failure(experiment, state)
        self._record_performance(state, mode)

    def _record_failure(self, experiment: Any, state: Poe2HybridProductState) -> None:
        reason = state.reason
        if not reason or reason in {"recovery_required", "stopped"}:
            return
        key = (state.recovery_revision, reason)
        if key in self._recorded_failures:
            return
        self._recorded_failures.add(key)
        if self._failure_recorder is None or self._snapshot is None:
            return
        try:
            path = self._failure_recorder.record(
                experiment=experiment,
                state=state,
                snapshot=self._snapshot,
            )
        except Exception as exc:
            if self._logger is not None:
                self._logger.exception(
                    "step=product_localization.failure_snapshot_failed reason=%s error=%s",
                    reason,
                    exc,
                )
        else:
            self._log(
                "step=product_localization.failure_snapshot path=%s reason=%s revision=%s",
                path,
                reason,
                state.recovery_revision,
            )

    def _record_performance(self, state: Poe2HybridProductState, mode: Any) -> None:
        self._tick_count += 1
        self._elapsed_total_ms += state.frame_elapsed_ms
        self._elapsed_max_ms = max(self._elapsed_max_ms, state.frame_elapsed_ms)
        for name in ("capture_ms", "evidence_ms", "localization_ms"):
            self._segment_totals[name] = self._segment_totals.get(name, 0.0) + float(
                state.diagnostics.get(name, 0.0)
            )
        if self._tick_count < self._performance_log_every:
            return
        elapsed_seconds = max(0.001, perf_counter() - self._performance_window_started)
        self._log(
            "step=product_localization.performance frames=%s average_ms=%.1f "
            "max_ms=%.1f actual_fps=%.1f capture_ms=%.1f evidence_ms=%.1f "
            "localization_ms=%.1f mode=%s source=%s",
            self._tick_count,
            self._elapsed_total_ms / self._tick_count,
            self._elapsed_max_ms,
            self._tick_count / elapsed_seconds,
            self._segment_totals.get("capture_ms", 0.0) / self._tick_count,
            self._segment_totals.get("evidence_ms", 0.0) / self._tick_count,
            self._segment_totals.get("localization_ms", 0.0) / self._tick_count,
            mode,
            state.source,
        )
        self._reset_performance_window()

    def _reset_performance_window(self) -> None:
        self._tick_count = 0
        self._elapsed_total_ms = 0.0
        self._elapsed_max_ms = 0.0
        self._performance_window_started = perf_counter()
        self._segment_totals = {}


__all__ = ["Poe2HybridProductRuntime", "Poe2HybridProductState"]
