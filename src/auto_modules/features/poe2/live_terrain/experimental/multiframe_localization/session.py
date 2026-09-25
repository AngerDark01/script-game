"""Timer-agnostic multi-frame experiment session with bounded background registration."""

from __future__ import annotations

from concurrent.futures import Future, ThreadPoolExecutor
import copy
import time
from typing import Any, Callable

from auto_modules.features.poe2.live_terrain.logging_utils import get_terrain_logger

from .coordinator import LocalizationPhase, MultiframeLocalizationCoordinator
from .models import MultiFrameEvidence, PositionEstimate


class MultiframeLocalizationSession:
    def __init__(
        self,
        *,
        frame_source: Any,
        evidence_builder: Any,
        config_provider: Callable[[], Any],
        coordinator: MultiframeLocalizationCoordinator,
        anchor_provider: Any,
        clock_ms: Callable[[], int],
        executor: Any | None = None,
        registration_timeout_ms: int = 10_000,
    ) -> None:
        if int(registration_timeout_ms) <= 0:
            raise ValueError("registration_timeout_ms must be positive")
        self.frame_source = frame_source
        self.evidence_builder = evidence_builder
        self.config_provider = config_provider
        self.coordinator = coordinator
        self.anchor_provider = anchor_provider
        self.clock_ms = clock_ms
        self.active = False
        self._previous = None
        self._frame_id = 0
        self.last_estimate: PositionEstimate | None = None
        self._anchor_revisions: set[int] = set()
        # A timed-out registration is detached and allowed to finish in the
        # background while the current run submits a fresh isolated attempt.
        self._executor = executor or ThreadPoolExecutor(max_workers=2, thread_name_prefix="poe2-multiframe")
        self._owns_executor = executor is None
        self._registration_future: Future | None = None
        self._generation = 0
        self._registration_generation: int | None = None
        self._registration_token = None
        self._registration_started_monotonic: float | None = None
        self._registration_timeout_reported = False
        self._retired_registration_futures: set[Future] = set()
        self.registration_timeout_ms = int(registration_timeout_ms)
        self._last_readiness_log_key = None
        self._logger = get_terrain_logger()
        self.last_tick_elapsed_ms = 0.0
        self.last_registration_elapsed_ms = 0.0

    @property
    def registration_pending(self) -> bool:
        return (
            self._registration_future is not None
            and not self._registration_future.done()
            and not self._registration_timeout_reported
        )

    def start(self) -> None:
        if self.active or self._registration_future is not None:
            self.stop()
        self._previous = None
        self._frame_id = 0
        self.last_estimate = None
        self._anchor_revisions.clear()
        reset_builder = getattr(self.evidence_builder, "reset", None)
        if callable(reset_builder):
            reset_builder()
        self.coordinator.reset()
        self._generation += 1
        self.coordinator.start()
        self.active = True

    def stop(self) -> None:
        self.active = False
        self._generation += 1
        if self._registration_future is not None:
            future = self._registration_future
            if not future.cancel() and not future.done():
                self._retired_registration_futures.add(future)
                future.add_done_callback(self._retired_registration_finished)
            self._registration_future = None
            self._registration_generation = None
            self._registration_token = None
            self._registration_started_monotonic = None
            self._registration_timeout_reported = False
        self.coordinator.stop()

    def reset(self) -> None:
        self.stop()
        self._previous = None
        self._frame_id = 0
        self.last_estimate = None
        self._anchor_revisions.clear()
        reset_builder = getattr(self.evidence_builder, "reset", None)
        if callable(reset_builder):
            reset_builder()
        self.coordinator.reset()

    def close(self) -> None:
        self.stop()
        if self._owns_executor:
            self._executor.shutdown(wait=False, cancel_futures=True)

    def anchor_once(self) -> bool:
        if not self.active:
            raise RuntimeError("session is not running")
        revision = self.coordinator.recovery_revision
        if revision in self._anchor_revisions:
            return False
        if self.coordinator.phase not in {LocalizationPhase.ANCHORING, LocalizationPhase.RECOVERING}:
            return False
        self._anchor_revisions.add(revision)
        try:
            anchor = self.anchor_provider.read_once(self.coordinator.instance_id)
            self.coordinator.accept_anchor(anchor)
        except Exception as exc:
            self.coordinator.anchor_failed(f"anchor_failed:{exc}")
            raise
        return True

    def tick(self) -> PositionEstimate:
        started = time.perf_counter()
        if not self.active:
            raise RuntimeError("multiframe localization session is not running")
        self._publish_finished_registration()
        self._expire_registration_if_needed()
        if self.coordinator.phase in {LocalizationPhase.ANCHORING, LocalizationPhase.RECOVERING}:
            self.anchor_once()
        if self.coordinator.phase is LocalizationPhase.WAITING:
            if self.coordinator.last_estimate is None:
                self.last_estimate = self.coordinator.anchor_failed("waiting")
            else:
                self.last_estimate = self.coordinator.last_estimate
            self.last_tick_elapsed_ms = (time.perf_counter() - started) * 1000.0
            return self.last_estimate

        config = self.config_provider()
        raw = self.frame_source.capture(config)
        self._frame_id += 1
        evidence = self.evidence_builder.build(raw, config, frame_id=self._frame_id, previous=self._previous)
        if not isinstance(evidence, MultiFrameEvidence):
            raise TypeError("evidence_builder must return MultiFrameEvidence")
        self._previous = evidence
        self.last_estimate = self.coordinator.ingest(evidence, defer_registration=True)
        self._schedule_registration_if_ready()
        self.last_tick_elapsed_ms = (time.perf_counter() - started) * 1000.0
        return self.last_estimate

    def _schedule_registration_if_ready(self) -> None:
        if self._registration_future is not None:
            return
        # Bound detached work: one current attempt plus at most one retired
        # attempt may exist, so repeated timeouts cannot build an unbounded
        # executor queue.
        if len(self._retired_registration_futures) >= 2:
            self._logger.warning("step=multiframe.registration_deferred reason=retired_worker_limit")
            return
        request = self.coordinator.prepare_registration_request()
        if request is None:
            window = self.coordinator.window
            readiness_key = (
                int(getattr(window, "version", 0)),
                len(window.snapshot()),
                int(self.coordinator.minimum_registration_frames),
            )
            if readiness_key != self._last_readiness_log_key:
                self._last_readiness_log_key = readiness_key
                self._logger.info(
                    "step=multiframe.registration_deferred evidence_version=%s keyframes=%s required_frames=%s phase=%s",
                    readiness_key[0],
                    readiness_key[1],
                    readiness_key[2],
                    self.coordinator.phase.value,
                )
            return
        self._last_readiness_log_key = None
        self._registration_generation = self._generation
        self._registration_token = request.token
        self._registration_started_monotonic = time.perf_counter()
        self._registration_timeout_reported = False
        self._logger.info(
            "step=multiframe.registration_submitted token=%s frame_count=%s strategy_a=%s strategy_b=%s",
            request.token,
            len(request.frames),
            self.coordinator.strategy_a_enabled,
            self.coordinator.strategy_b_enabled,
        )
        try:
            evaluation_coordinator = self._isolated_evaluation_coordinator()
        except Exception as exc:
            self.coordinator.phase = LocalizationPhase.COLLECTING
            self.coordinator._pending_token = None
            self._logger.exception(
                "step=multiframe.registration_not_submitted reason=isolated_copy_failed error=%s",
                exc,
            )
            return
        self._registration_future = self._executor.submit(
            self._evaluate_timed,
            request,
            evaluation_coordinator,
        )

    def _isolated_evaluation_coordinator(self) -> MultiframeLocalizationCoordinator:
        """Copy mutable strategies so timed-out workers cannot poison a new run."""
        isolated = copy.copy(self.coordinator)
        isolated.strategy_a = copy.deepcopy(self.coordinator.strategy_a)
        isolated.strategy_b = copy.deepcopy(self.coordinator.strategy_b)
        return isolated

    def _evaluate_timed(self, request, evaluation_coordinator):
        started = time.perf_counter()
        self._logger.info(
            "step=multiframe.registration_started token=%s frame_count=%s",
            request.token,
            len(request.frames),
        )
        try:
            outcome = evaluation_coordinator.evaluate_registration(request)
        except Exception:
            self._logger.exception(
                "step=multiframe.registration_failed token=%s elapsed_ms=%.2f",
                request.token,
                (time.perf_counter() - started) * 1000.0,
            )
            raise
        elapsed_ms = (time.perf_counter() - started) * 1000.0
        self._logger.info(
            "step=multiframe.registration_finished token=%s elapsed_ms=%.2f source=%s has_registration=%s strategy_a_status=%s strategy_a_reason=%s strategy_b_candidates=%s diagnostics=%s",
            request.token,
            elapsed_ms,
            outcome.source,
            outcome.registration is not None,
            getattr(outcome.strategy_a, "status", None),
            getattr(outcome.strategy_a, "reason", None),
            len(getattr(outcome.strategy_b, "candidates", ()) or ()),
            dict(outcome.diagnostics or {}),
        )
        return outcome, elapsed_ms

    def _expire_registration_if_needed(self) -> None:
        future = self._registration_future
        started = self._registration_started_monotonic
        if future is None or future.done() or started is None or self._registration_timeout_reported:
            return
        elapsed_ms = (time.perf_counter() - started) * 1000.0
        if elapsed_ms < self.registration_timeout_ms:
            return
        self._registration_timeout_reported = True
        self.last_registration_elapsed_ms = elapsed_ms
        if self.coordinator.phase is LocalizationPhase.REGISTERING:
            self.coordinator.phase = LocalizationPhase.COLLECTING
        self.last_estimate = self.coordinator._estimate(
            "registration_timeout",
            status="collecting",
        )
        self._logger.warning(
            "step=multiframe.registration_timeout token=%s elapsed_ms=%.2f timeout_ms=%s",
            self._registration_token,
            elapsed_ms,
            self.registration_timeout_ms,
        )
        # Future.cancel() cannot stop a running worker. Detach it from the
        # active slot only after the worker has its own coordinator copy.
        self._retired_registration_futures.add(future)
        self._registration_future = None
        self._registration_generation = None
        self._registration_token = None
        self._registration_started_monotonic = None
        self._registration_timeout_reported = False
        future.add_done_callback(self._retired_registration_finished)

    def _retired_registration_finished(self, future: Future) -> None:
        self._retired_registration_futures.discard(future)
        if future.cancelled():
            return
        try:
            future.result()
        except Exception:
            self._logger.exception("step=multiframe.retired_registration_failed")
        else:
            self._logger.info("step=multiframe.retired_registration_finished")

    def _publish_finished_registration(self) -> None:
        future = self._registration_future
        if future is None or not future.done():
            return
        self._registration_future = None
        scheduled_generation = self._registration_generation
        self._registration_generation = None
        self._registration_token = None
        timed_out = self._registration_timeout_reported
        self._registration_started_monotonic = None
        self._registration_timeout_reported = False
        if future.cancelled():
            return
        if scheduled_generation != self._generation:
            self._logger.info("step=multiframe.registration_discarded reason=stale_generation")
            return
        if timed_out:
            self._logger.warning("step=multiframe.registration_discarded reason=timeout")
            return
        try:
            outcome, self.last_registration_elapsed_ms = future.result()
        except Exception as exc:
            self.coordinator.phase = LocalizationPhase.COLLECTING
            self.last_estimate = self.coordinator._estimate(f"registration_failed:{exc}", status="collecting")
            self._logger.exception("step=multiframe.registration_result_failed error=%s", exc)
            return
        self.last_estimate = self.coordinator.apply_registration_outcome(outcome)
        self._logger.info(
            "step=multiframe.registration_published token=%s status=%s reason=%s",
            outcome.request.token,
            self.last_estimate.status,
            self.last_estimate.reason,
        )


__all__ = ["MultiframeLocalizationSession"]
