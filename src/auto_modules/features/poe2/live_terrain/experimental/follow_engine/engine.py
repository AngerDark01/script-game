"""UI-independent composition port for the dual-channel follow engine."""

from __future__ import annotations

from dataclasses import dataclass
from concurrent.futures import Future, ThreadPoolExecutor, TimeoutError as FutureTimeoutError
import logging
import math
import threading
import time
from typing import Any, Callable, Mapping, Protocol

from .contracts import FusionSnapshot
from .execution_feedback import ExecutionReceipt
from .generation import GenerationClock, GenerationToken
from .relay import RelayLoop
from .timing import TimingWindow
from .diagnostic_events import DiagnosticRelay


_LOGGER = logging.getLogger("auto_modules.poe2_live_terrain.follow_engine")


class VisionPort(Protocol):
    def start(self, *, generation: int, map_instance: str) -> None: ...

    def poll_latest(self) -> Any: ...

    def stop(self, *, timeout: float = 2.0) -> None: ...


class ControlPort(Protocol):
    def start(self, *, generation: int, map_instance: str) -> None: ...

    def send_visual(self, observation: Any, *, frame: object | None = None) -> None: ...

    def send_execution(self, receipt: ExecutionReceipt) -> None: ...

    def update_target(self, role_id: str, target: tuple[float, float] | None) -> None: ...

    def poll_latest(self) -> Any: ...

    def stop(self, *, timeout: float = 2.0) -> None: ...


class OutputPort(Protocol):
    def start(self) -> None: ...

    def apply(self, snapshot: FusionSnapshot) -> None: ...

    def stop(self, *, force: bool = True) -> None: ...

    def neutralize(self) -> None: ...

    def poll_receipts(self) -> tuple[ExecutionReceipt, ...]: ...


@dataclass(slots=True)
class RebuildBundle:
    """Detached worker generation prepared off-thread and committed safely."""

    vision: VisionPort
    control: ControlPort
    commit: Callable[[], None] | None = None
    dispose: Callable[[], None] | None = None
    retire: Callable[[], None] | None = None

    def close(self) -> None:
        if self.dispose is not None:
            self.dispose()
            return
        for component in (self.vision, self.control):
            dispose = getattr(component, "dispose", None)
            try:
                (dispose if callable(dispose) else component.stop)()
            except Exception:
                _LOGGER.exception("step=follow_engine.rebuild_bundle_dispose_failed")


@dataclass(frozen=True, slots=True)
class FollowEngineStart:
    map_instance: str
    roles: Mapping[str, int]

    def __post_init__(self) -> None:
        instance = str(self.map_instance).strip()
        roles = {str(role).strip(): int(controller) for role, controller in self.roles.items()}
        if not instance or not roles or any(not role or controller < 1 for role, controller in roles.items()):
            raise ValueError("follow engine start configuration is invalid")
        object.__setattr__(self, "map_instance", instance)
        object.__setattr__(self, "roles", roles)


class FollowEnginePort:
    """Own process handles and output lease without exposing their internals to UI."""

    def __init__(
        self,
        *,
        vision: VisionPort,
        control: ControlPort,
        output: OutputPort,
        generation_clock: GenerationClock | None = None,
        rebuild_factory: Callable[[], tuple[VisionPort, ControlPort] | RebuildBundle] | None = None,
        startup_timeout_ms: int = 10_000,
        stall_timeout_ms: int = 2_000,
        rebuild_backoff_ms: int = 1_000,
        max_rebuild_attempts: int = 3,
        live_target_min_confidence: float = 0.2,
        control_owns_live_targets: bool = False,
    ) -> None:
        self.vision = vision
        self.control = control
        self.output = output
        self.clock = generation_clock or GenerationClock()
        self.token: GenerationToken | None = None
        self._active = False
        self._output_state = "stopped"
        self._output_diagnostics: dict[str, object] = {}
        self._last_snapshot: FusionSnapshot | None = None
        # Latest encoded frame retained for the page's read-only preview.  The
        # control path never consumes this value; Vision/Control ownership and
        # cadence remain unchanged.
        self._last_preview_frame: Any | None = None
        self._last_preview_sequence: int = -1
        # Latest accepted vision DTO, including its registration transform.
        # Rebuild factories use this immutable handover value so a stalled
        # worker does not restart with the first-frame transform.
        self._last_visual_observation: Any | None = None
        self._last_error: str = ""
        self._first_fault: dict[str, object] | None = None
        self._reported_faults: dict[str, str] = {}
        self._rebuild_fault_signatures: set[tuple[str, int, int, str]] = set()
        self._last_stall_report: object = None
        self._worker_state = {"vision": "stopped", "control": "stopped"}
        self._rebuild_factory = rebuild_factory
        self._startup_timeout_ms = max(100, int(startup_timeout_ms))
        self._stall_timeout_ms = max(100, int(stall_timeout_ms))
        self._rebuild_backoff_ms = max(0, int(rebuild_backoff_ms))
        self._max_rebuild_attempts = max(1, int(max_rebuild_attempts))
        self._started_monotonic = 0.0
        self._last_progress_monotonic = {"vision": 0.0, "control": 0.0}
        self._last_parent_poll_monotonic = 0.0
        self._parent_poll_count = 0
        self._last_parent_event = {"vision": None, "control": None}
        self._worker_ready = {"vision": False, "control": False}
        self._rebuild_in_progress = False
        self._rebuild_count = 0
        self._rebuild_attempts = 0
        self._next_rebuild_monotonic = 0.0
        self._rebuild_future: Future | None = None
        self._rebuild_executor: ThreadPoolExecutor | None = None
        self._retiring_rebuild_futures: set[Future] = set()
        self._target_cache: dict[str, tuple[float, float] | None] = {}
        self._live_target_source: str | None = None
        self._live_target_roles: tuple[str, ...] = ()
        self._live_target_last: tuple[float, float] | None = None
        self._live_target_last_capture_ms: int | None = None
        self._lifecycle_lock = threading.RLock()
        self._session_epoch = 0
        self._rebuild_cancel = threading.Event()
        self._rebuild_attempt_timing = TimingWindow(128)
        self._rebuild_commit_timing = TimingWindow(128)
        self._rebuild_retire_timing = TimingWindow(128)
        self._first_vision_logged = False
        self._first_snapshot_logged = False
        self._first_output_logged = False
        self._first_target_logged = False
        self._last_control_diagnostics: dict[str, object] = {}
        self._last_control_log_signature: tuple[object, ...] | None = None
        self._output_restart_attempts = 0
        self._next_output_restart_monotonic = 0.0
        self._output_restart_lock = threading.Lock()
        if not math.isfinite(float(live_target_min_confidence)) or not 0.0 <= float(live_target_min_confidence) <= 1.0:
            raise ValueError("live_target_min_confidence must be within [0, 1]")
        self._live_target_min_confidence = float(live_target_min_confidence)
        self._control_owns_live_targets = bool(control_owns_live_targets)
        self._live_target_initial_position: tuple[float, float] | None = None
        self._relay: RelayLoop | None = None
        self._relay_snapshot_lock = threading.Lock()
        self._poll_lock = threading.Lock()
        self._snapshot_event = threading.Event()
        self._diagnostic_relay = DiagnosticRelay(_LOGGER)

    @property
    def active(self) -> bool:
        # Async output startup is intentionally non-blocking.  Refreshing the
        # health state here prevents a failed actor from being reported as an
        # active engine when callers inspect the port between UI polls.
        self._refresh_output_health()
        return self._active

    def start(self, config: FollowEngineStart) -> GenerationToken:
        # A canceled rebuild can still be inside a component's bounded stop
        # call.  Do not reuse those handles for a new session until the old
        # future has actually exited; otherwise its late stop may kill the new
        # session's workers.
        if not self._await_retiring_rebuilds(timeout=2.5):
            raise RuntimeError("previous worker rebuild is still shutting down")
        with self._lifecycle_lock:
            if self._active:
                raise RuntimeError("follow engine is already active")
            self._session_epoch += 1
            session_epoch = self._session_epoch
            self._rebuild_cancel = threading.Event()
        token = self.clock.begin(config.map_instance)
        attempted = []
        stage = "control"
        started = time.perf_counter()
        try:
            for stage, component in (("control", self.control), ("vision", self.vision), ("output", self.output)):
                attempted.append((stage, component))
                stage_started = time.perf_counter()
                _LOGGER.info(
                    "step=follow_engine.start_stage stage=%s outcome=begin generation=%s instance=%s",
                    stage, token.generation, token.map_instance,
                )
                if stage == "output":
                    component.start()
                    self._output_state = "starting"
                else:
                    component.start(generation=token.generation, map_instance=token.map_instance)
                _LOGGER.info(
                    "step=follow_engine.start_stage stage=%s outcome=completed elapsed_ms=%.3f",
                    stage, (time.perf_counter() - stage_started) * 1000,
                )
        except Exception as exc:
            _LOGGER.exception("step=follow_engine.start_failed stage=%s elapsed_ms=%.3f",
                              stage, (time.perf_counter() - started) * 1000)
            # A component may allocate resources before its start raises.
            # Stop it too, then continue cleanup even if any stop also fails.
            cleanup = [("output", self.output)] + [
                item for item in reversed(attempted) if item[0] != "output"
            ]
            for name, component in cleanup:
                try:
                    if name == "output":
                        component.stop(force=True)
                    else:
                        component.stop()
                except Exception:
                    _LOGGER.exception("step=follow_engine.start_cleanup_failed component=%s", name)
            self._active = False
            self._output_state = "failed" if stage == "output" else "stopped"
            self.token = None
            self._last_snapshot = None
            self._last_visual_observation = None
            self._last_error = f"{stage}_start_failed: {type(exc).__name__}: {exc}"
            self._worker_state = {"vision": "stopped", "control": "stopped"}
            self.clock.stop()
            raise
        self.token = token
        self._active = True
        if not callable(getattr(self.output, "diagnostics", None)):
            # Synchronous OutputPort implementations do not expose an actor
            # state.  They are considered running once start() returned.
            self._output_state = "running"
        self._started_monotonic = time.monotonic()
        self._last_progress_monotonic = {"vision": self._started_monotonic, "control": self._started_monotonic}
        self._worker_ready = {"vision": False, "control": False}
        self._last_snapshot = None
        self._snapshot_event.clear()
        self._last_visual_observation = None
        self._last_preview_frame = None
        self._last_preview_sequence = -1
        self._last_error = ""
        self._first_fault = None
        self._reported_faults.clear()
        self._rebuild_fault_signatures.clear()
        self._last_stall_report = None
        self._worker_state = {"vision": "running", "control": "running"}
        self._first_vision_logged = False
        self._first_snapshot_logged = False
        self._first_output_logged = False
        self._first_target_logged = False
        self._output_restart_attempts = 0
        self._next_output_restart_monotonic = 0.0
        self._rebuild_attempts = 0
        self._rebuild_count = 0
        self._next_rebuild_monotonic = 0.0
        if self._live_target_initial_position is not None:
            self._publish_live_target(self._live_target_initial_position, captured_at_ms=None)
        self._relay = RelayLoop(self._poll_once, interval_ms=10, on_error=self._on_relay_error)
        self._relay.start(epoch=session_epoch)
        _LOGGER.info("step=follow_engine.start_completed generation=%s elapsed_ms=%.3f",
                     token.generation, (time.perf_counter() - started) * 1000)
        return token

    def configure_live_target_policy(
        self,
        *,
        source_role: str | None,
        target_roles: tuple[str, ...] | list[str] = (),
        initial_position: tuple[float, float] | None = None,
    ) -> None:
        """Configure a generic observation-to-target stream for this session."""
        source = None if source_role is None else str(source_role).strip()
        targets = tuple(str(role).strip() for role in target_roles if str(role).strip())
        if source is None or not targets:
            self._live_target_source = None
            self._live_target_roles = ()
            self._live_target_last = None
            self._live_target_last_capture_ms = None
            self._live_target_initial_position = None
            return
        if initial_position is not None:
            point = (float(initial_position[0]), float(initial_position[1]))
            if not all(math.isfinite(value) for value in point):
                raise ValueError("initial live target position must be finite")
            self._live_target_last = point
            self._live_target_initial_position = point
        else:
            self._live_target_last = None
            self._live_target_initial_position = None
        self._live_target_last_capture_ms = None
        self._live_target_source = source
        self._live_target_roles = targets
        if self._active and self._live_target_initial_position is not None:
            self._publish_live_target(self._live_target_initial_position, captured_at_ms=None)

    def _publish_live_target(
        self,
        target: tuple[float, float],
        *,
        captured_at_ms: int | None,
    ) -> None:
        """Publish one target to every follower role without UI involvement."""

        normalized = (float(target[0]), float(target[1]))
        self._live_target_last = normalized
        if captured_at_ms is not None:
            self._live_target_last_capture_ms = int(captured_at_ms)
        if self._control_owns_live_targets:
            return
        for role_id in self._live_target_roles:
            if role_id == self._live_target_source:
                continue
            try:
                self.update_target(normalized, role_id=role_id)
            except RuntimeError:
                # An explicit stop may win the lifecycle race.
                return

    def _forward_live_target_observation(self, observation: Any) -> None:
        # In the modular composition the control worker owns this policy and
        # can update the follower target in the same tick as it accepts the
        # visual source.  Relaying the same observation through the UI would
        # reintroduce a timer-sized delay and could overwrite the fresh target
        # with a stale queue item.
        if self._control_owns_live_targets:
            return
        source = self._live_target_source
        if source is None or not self._live_target_roles:
            return
        roles = getattr(observation, "roles", None)
        source_observation = roles.get(source) if isinstance(roles, Mapping) else None
        point = getattr(source_observation, "position_native", None)
        if (
            not bool(getattr(source_observation, "visible", False))
            or point is None
            or float(getattr(source_observation, "confidence", 0.0)) < self._live_target_min_confidence
        ):
            return
        captured_at_ms = int(getattr(observation, "captured_at_ms", 0))
        if self._live_target_last_capture_ms is not None and captured_at_ms <= self._live_target_last_capture_ms:
            return
        target = (float(point[0]), float(point[1]))
        if self._live_target_last is not None and math.dist(target, self._live_target_last) < 0.05:
            return
        self._publish_live_target(target, captured_at_ms=captured_at_ms)
        _LOGGER.debug(
            "step=follow_engine.live_target_observation source=%s target=%s generation=%s",
            source, target, self.token.generation if self.token is not None else None,
        )

    def update_target(self, target: tuple[float, float] | None, *, role_id: str | None = None) -> None:
        if not self._active:
            raise RuntimeError("follow engine is not active")
        if role_id is None:
            raise ValueError("role_id is required when updating a composed engine")
        normalized = None if target is None else (float(target[0]), float(target[1]))
        with self._lifecycle_lock:
            if not self._active:
                raise RuntimeError("follow engine is not active")
            self._target_cache[str(role_id)] = normalized
            if not self._first_target_logged:
                self._first_target_logged = True
                _LOGGER.info(
                    "step=follow_engine.first_target_update role=%s target=%s generation=%s",
                    role_id, normalized, self.token.generation if self.token is not None else None,
                )
        self.control.update_target(str(role_id), normalized)

    def _poll_once(self) -> FusionSnapshot | None:
        """Serialize all worker queue consumption through one owner."""
        if not self._poll_lock.acquire(blocking=False):
            return self._last_snapshot
        try:
            return self._poll_once_unlocked()
        finally:
            self._poll_lock.release()

    def _poll_once_unlocked(self) -> FusionSnapshot | None:
        """Drain latest vision/control events without waiting on either process."""
        poll_started = time.monotonic()
        self._parent_poll_count += 1
        poll_gap_ms = (
            0.0 if self._last_parent_poll_monotonic <= 0.0
            else (poll_started - self._last_parent_poll_monotonic) * 1000.0
        )
        self._last_parent_poll_monotonic = poll_started
        if self._parent_poll_count == 1 or self._parent_poll_count % 30 == 0:
            _LOGGER.info(
                "step=follow_engine.parent_poll count=%s gap_ms=%.1f active=%s worker_state=%s progress_age_ms=%s",
                self._parent_poll_count, poll_gap_ms, self._active, dict(self._worker_state),
                {name: round((poll_started - stamp) * 1000.0, 1) if stamp else None
                 for name, stamp in self._last_progress_monotonic.items()},
            )
        # Commit completed replacements before capturing handles.  While a
        # replacement is being built its old queues are being disposed; they
        # are not valid consumers, even though the follow session stays active.
        self._collect_rebuild_result()
        with self._lifecycle_lock:
            active = self._active
            vision = self.vision
            control = self.control
            poll_epoch = self._session_epoch
            rebuilding = self._rebuild_in_progress or self._rebuild_future is not None
        if not active:
            return self._last_snapshot
        self._refresh_output_health()
        if not self._active:
            return self._last_snapshot
        if rebuilding:
            return self._last_snapshot
        self._refresh_worker_liveness()
        self._forward_execution_receipts()
        vision_event = None
        try:
            vision_event = vision.poll_latest()
        except Exception as exc:
            if not self._is_closed_queue_error(exc):
                raise
            self._mark_worker_queue_fault("vision", exc)
        if vision_event is not None and getattr(vision_event, "kind", "") == "observation":
            self._worker_state["vision"] = "running"
            self._last_progress_monotonic["vision"] = time.monotonic()
            self._last_parent_event["vision"] = int(getattr(vision_event, "sequence", -1))
            self._worker_ready["vision"] = True
            self._reported_faults.pop("vision", None)
            self._rebuild_fault_signatures = {
                item for item in self._rebuild_fault_signatures if item[0] != "vision"
            }
            if not self._first_vision_logged:
                self._first_vision_logged = True
                _LOGGER.info(
                    "step=follow_engine.first_vision_observation generation=%s elapsed_ms=%.3f",
                    self.token.generation if self.token is not None else None,
                    (time.monotonic() - self._started_monotonic) * 1000.0,
                )
            observation = getattr(vision_event, "observation", None)
            if observation is not None:
                # Keep the observation only for the active generation.  The
                # rebuild thread reads this under the lifecycle lock while
                # constructing replacement vision/local-recovery workers.
                with self._lifecycle_lock:
                    current_observation = (
                        self._active
                        and self._session_epoch == poll_epoch
                        and self.token is not None
                        and int(getattr(observation, "generation", -1)) == int(self.token.generation)
                        and str(getattr(observation, "map_instance", "")) == str(self.token.map_instance)
                    )
                    if current_observation:
                        self._last_visual_observation = observation
                if current_observation:
                    self._diagnostic_relay.consume("vision", (poll_epoch, observation.generation),
                        getattr(vision_event, "diagnostic_events", ()))
                control_frame = getattr(vision_event, "frame", None)
                frame = control_frame
                if frame is None:
                    # Normal modular Vision publishes bytes to the shared ring
                    # and sends only the observation header over the queue.
                    # Mirror the newest payload for UI display without making
                    # the UI a worker-queue consumer.
                    ring = getattr(vision, "frame_ring", None)
                    read_latest = getattr(ring, "read_latest", None)
                    if callable(read_latest):
                        try:
                            frame = read_latest(after_sequence=self._last_preview_sequence)
                        except Exception:
                            frame = None
                if frame is not None:
                    sequence = int(getattr(frame, "sequence", -1))
                    if sequence > self._last_preview_sequence:
                        self._last_preview_frame = frame
                        self._last_preview_sequence = sequence
                # A ring record is only for the UI preview. Control keeps its
                # existing observation/header path and resolves ring bytes in
                # the child, so preview polling cannot alter localization.
                if control_frame is None:
                    control.send_visual(observation)
                else:
                    control.send_visual(observation, frame=control_frame)
                # Propagate a fresh source-role target before reading the
                # control snapshot.  The previous page-only propagation ran
                # after the snapshot and therefore added at least one UI
                # interval of target age.
                self._forward_live_target_observation(observation)
        elif vision_event is not None:
            vision_kind = str(getattr(vision_event, "kind", ""))
            if vision_kind == "error":
                self._worker_state["vision"] = "error"
                self._last_error = str(getattr(vision_event, "error", "vision_error"))
                self._record_worker_fault("vision", self._last_error, getattr(vision_event, "traceback_text", ""))
            elif vision_kind == "stopped":
                self._worker_state["vision"] = "stopped"

        control_event = None
        try:
            control_event = control.poll_latest()
        except Exception as exc:
            if not self._is_closed_queue_error(exc):
                raise
            self._mark_worker_queue_fault("control", exc)
        if control_event is None:
            self._check_worker_stall()
            return self._last_snapshot
        kind = str(getattr(control_event, "kind", ""))
        if kind == "snapshot":
            self._worker_state["control"] = "running"
            self._last_progress_monotonic["control"] = time.monotonic()
            self._worker_ready["control"] = True
            self._reported_faults.pop("control", None)
            if not self._first_snapshot_logged:
                self._first_snapshot_logged = True
                _LOGGER.info(
                    "step=follow_engine.first_control_snapshot generation=%s elapsed_ms=%.3f",
                    self.token.generation if self.token is not None else None,
                    (time.monotonic() - self._started_monotonic) * 1000.0,
                )
            snapshot = getattr(control_event, "snapshot", None)
            control_tick = int(getattr(control_event, "tick_sequence", 0) or 0)
            self._last_parent_event["control"] = control_tick if control_tick > 0 else (
                int(getattr(snapshot, "tick_sequence", -1)) if snapshot is not None else None
            )
            event_diagnostics = getattr(control_event, "diagnostics", None)
            if isinstance(event_diagnostics, dict):
                self._last_control_diagnostics = dict(event_diagnostics)
                self._diagnostic_relay.consume("control", (poll_epoch, getattr(snapshot, "generation", None)),
                    event_diagnostics.get("diagnostic_events", ()))
                decision = self._last_control_diagnostics.get("last_control_decision")
                if isinstance(decision, dict):
                    signature = (
                        decision.get("recovery_state"),
                        decision.get("recovery_reason"),
                        tuple(
                            (role.get("source"), tuple(role.get("last_vector", ())) == (0.0, 0.0))
                            for role in (decision.get("roles") or {}).values()
                            if isinstance(role, dict)
                        ),
                    )
                    if control_tick <= 1 or control_tick % 30 == 0 or signature != self._last_control_log_signature:
                        _LOGGER.info(
                            "step=follow_engine.control_decision_observed tick=%s recovery=%s reason=%s details=%s",
                            control_tick,
                            decision.get("recovery_state"),
                            decision.get("recovery_reason"),
                            decision,
                        )
                    self._last_control_log_signature = signature
            if snapshot is not None:
                self._last_snapshot = snapshot
                self._snapshot_event.set()
                with self._lifecycle_lock:
                    current = self._active and self._session_epoch == poll_epoch and self.control is control
                if current:
                    try:
                        self.output.apply(snapshot)
                        if not self._first_output_logged:
                            self._first_output_logged = True
                            _LOGGER.info(
                                "step=follow_engine.first_output_apply generation=%s elapsed_ms=%.3f",
                                self.token.generation if self.token is not None else None,
                                (time.monotonic() - self._started_monotonic) * 1000.0,
                            )
                    except Exception as exc:
                        self._last_error = f"output_apply_failed: {type(exc).__name__}: {exc}"
                        self._neutralize_output()
                else:
                    return self._last_snapshot
                self._forward_execution_receipts()
                self._check_worker_stall()
                return snapshot
        elif kind == "error":
            self._worker_state["control"] = "error"
            self._last_error = str(getattr(control_event, "error", "control_error"))
            self._record_worker_fault("control", self._last_error, getattr(control_event, "traceback_text", ""))
            self._neutralize_output()
        elif kind == "command_error":
            self._last_error = str(getattr(control_event, "error", "command_error"))
            self._record_worker_fault("control", self._last_error, getattr(control_event, "traceback_text", ""))
        elif kind == "stopped":
            self._worker_state["control"] = "stopped"
            self._neutralize_output()
        self._check_worker_stall()
        return self._last_snapshot

    def preview_frame(self) -> Any | None:
        """Return the newest encoded Vision frame for read-only UI preview."""
        return self._last_preview_frame

    def poll(self) -> FusionSnapshot | None:
        """Return the latest relay-owned snapshot without driving workers.

        Worker queues are drained by :class:`RelayLoop`; this method is safe to
        call from a paused or slow Qt timer and never becomes the transport
        clock.
        """
        # Compatibility/read-after-start edge: wait briefly for the relay's
        # first snapshot, without driving worker queues from the UI thread.
        if self._last_snapshot is None and self._active:
            self._snapshot_event.wait(timeout=0.05)
        return self._last_snapshot

    def _on_relay_error(self, error: BaseException) -> None:
        """Make an unexpected relay failure visible without stopping follow."""
        self._last_error = f"relay_error: {type(error).__name__}: {error}"
        _LOGGER.error("step=follow_engine.relay_error error=%s", self._last_error)

    def _record_worker_fault(self, worker: str, error: str, traceback_text: str = "") -> None:
        """Persist the original fault before recovery can replace last_error."""
        if self._reported_faults.get(worker) == error:
            return
        self._reported_faults[worker] = error
        handle = self.vision if worker == "vision" else self.control
        process = getattr(handle, "process", None)
        fault = {
            "worker": worker, "error": error,
            "generation": self.token.generation if self.token is not None else None,
            "session_epoch": self._session_epoch,
            "pid": getattr(process, "pid", None),
            "exitcode": getattr(process, "exitcode", None),
            "traceback": str(traceback_text or ""),
        }
        if self._first_fault is None:
            self._first_fault = fault
        _LOGGER.error("step=follow_engine.worker_fault details=%s", fault)

    @staticmethod
    def _is_closed_queue_error(error: BaseException) -> bool:
        text = str(error).lower()
        return isinstance(error, (ValueError, OSError)) and "queue" in text and "closed" in text

    def _mark_worker_queue_fault(self, name: str, error: BaseException) -> None:
        """Turn a disposed worker queue into a bounded recoverable fault."""
        worker = str(name)
        if worker not in self._worker_state:
            return
        self._worker_state[worker] = "stalled"
        self._last_progress_monotonic[worker] = 0.0
        self._last_error = f"{worker}_queue_closed: {type(error).__name__}: {error}"
        self._record_worker_fault(worker, self._last_error)
        if worker == "control":
            self._neutralize_output()

    def _check_worker_stall(self) -> None:
        """Classify silent workers and optionally start a bounded rebuild.

        This is a component watchdog only: it never ends the follow session
        and it never applies a business-task timeout.  A composition may opt
        into replacement by supplying ``rebuild_factory``; offline/fake
        compositions still receive a precise diagnostic state.
        """
        self._collect_rebuild_result()
        if not self._active or self._rebuild_in_progress or self._rebuild_future is not None:
            return
        now = time.monotonic()
        if now < self._next_rebuild_monotonic:
            return
        # Each process owns its own startup window.  A fast seeded Control
        # snapshot is not proof that Vision has completed its first capture.
        deadlines = {
            name: self._stall_timeout_ms if self._worker_ready[name] else self._startup_timeout_ms
            for name in self._last_progress_monotonic
        }
        stale = [name for name, stamp in self._last_progress_monotonic.items() if (now - stamp) * 1000.0 > deadlines[name]]
        if not stale:
            return
        _LOGGER.warning(
            "step=follow_engine.worker_stall_evidence workers=%s parent_poll_count=%s parent_poll_gap_ms=%s "
            "progress_age_ms=%s child_states=%s last_parent_event=%s deadlines_ms=%s",
            stale, self._parent_poll_count,
            round((now - self._last_parent_poll_monotonic) * 1000.0, 1) if self._last_parent_poll_monotonic else None,
            {name: round((now - stamp) * 1000.0, 1) if stamp else None
             for name, stamp in self._last_progress_monotonic.items()},
            dict(self._worker_state), dict(self._last_parent_event), deadlines,
        )
        for name in stale:
            self._worker_state[name] = "stalled"
        prior_fault = str(self._first_fault["error"]) if self._first_fault is not None else ""
        self._last_error = "worker_stall:" + ",".join(stale)
        if prior_fault:
            self._last_error += " cause=" + prior_fault
        report_key = (tuple(stale), self._rebuild_attempts, self._session_epoch)
        if report_key != self._last_stall_report:
            self._last_stall_report = report_key
            _LOGGER.warning(
                "step=follow_engine.worker_stall workers=%s ages_ms=%s deadline_ms=%s states=%s attempt=%s epoch=%s cause=%s",
                stale, {name: round((now - stamp) * 1000, 1) for name, stamp in self._last_progress_monotonic.items()},
                deadlines, dict(self._worker_state), self._rebuild_attempts, self._session_epoch, prior_fault,
            )
        if self._rebuild_factory is not None:
            # A deterministic child contract fault will survive a worker
            # replacement.  Rebuilding it repeatedly only churns processes,
            # neutralizes output and hides the original traceback.  Keep the
            # session alive in degraded/prediction mode and require the next
            # explicit session (or a changed generation) after one attempted
            # replacement for the same fault signature.
            fault_signature = prior_fault.strip()
            fault_key = (
                str(stale[0]) if len(stale) == 1 else ",".join(stale),
                int(self._session_epoch),
                int(getattr(self.token, "generation", 0) if self.token is not None else 0),
                fault_signature,
            )
            if fault_signature and fault_key in self._rebuild_fault_signatures:
                self._last_error = "worker_deterministic_fault:" + fault_signature
                self._worker_state = {
                    name: "failed" if name in stale else state
                    for name, state in self._worker_state.items()
                }
                _LOGGER.error(
                    "step=follow_engine.rebuild_suppressed deterministic_fault=%s attempts=%s epoch=%s",
                    fault_signature, self._rebuild_attempts, self._session_epoch,
                )
                return
            if self._rebuild_attempts >= self._max_rebuild_attempts:
                self._last_error = "worker_rebuild_budget_exhausted:" + ",".join(stale)
                self._worker_state = {name: "failed" if name in stale else state for name, state in self._worker_state.items()}
                return
            self._rebuild_attempts += 1
            if fault_signature:
                self._rebuild_fault_signatures.add(fault_key)
            _LOGGER.warning("step=follow_engine.rebuild_begin reason=%s attempt=%s epoch=%s", self._last_error, self._rebuild_attempts, self._session_epoch)
            self._next_rebuild_monotonic = now + self._rebuild_backoff_ms / 1000.0
            if self._rebuild_executor is None:
                self._rebuild_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="follow-worker-rebuild")
            self._rebuild_in_progress = True
            self._neutralize_output()
            token = self.token
            session_epoch = self._session_epoch
            cancel = self._rebuild_cancel
            self._rebuild_future = self._rebuild_executor.submit(
                self._rebuild_components, self._last_error, session_epoch, token, cancel,
            )

    def _collect_rebuild_result(self) -> None:
        future = self._rebuild_future
        if future is None or not future.done():
            return
        self._rebuild_future = None
        try:
            future.result()
        except Exception as exc:  # defensive: _rebuild_components also contains its own guard
            self._last_error = f"worker_rebuild_failed: {type(exc).__name__}: {exc}"
            self._worker_state = {"vision": "error", "control": "error"}
        finally:
            self._rebuild_in_progress = False

    def _rebuild_components(self, reason: str, session_epoch: int, token: GenerationToken | None,
                            cancel: threading.Event) -> None:
        attempt_started = time.perf_counter()
        if token is None or self._rebuild_factory is None:
            return

        def valid() -> bool:
            with self._lifecycle_lock:
                return (
                    not cancel.is_set()
                    and self._active
                    and self._session_epoch == session_epoch
                    and self.token == token
                )

        bundle: RebuildBundle | None = None
        try:
            with self._lifecycle_lock:
                old_vision, old_control = self.vision, self.control
            if not valid():
                return
            for component in (old_vision, old_control):
                try:
                    component.stop(timeout=2.0)
                except Exception:
                    _LOGGER.exception("step=follow_engine.rebuild_old_component_stop_failed")
                dispose = getattr(component, "dispose", None)
                if callable(dispose):
                    try:
                        dispose()
                    except Exception:
                        _LOGGER.exception("step=follow_engine.rebuild_old_component_dispose_failed")
            if not valid():
                return
            replacement = self._rebuild_factory()
            if isinstance(replacement, RebuildBundle):
                bundle = replacement
            else:
                vision, control = replacement
                bundle = RebuildBundle(vision, control)
            vision, control = bundle.vision, bundle.control
            if not valid():
                bundle.close()
                bundle = None
                return
            try:
                control.start(generation=token.generation, map_instance=token.map_instance)
                vision.start(generation=token.generation, map_instance=token.map_instance)
            except Exception:
                for component in (vision, control):
                    try:
                        component.stop(timeout=2.0)
                    except Exception:
                        _LOGGER.exception("step=follow_engine.rebuild_new_component_cleanup_failed")
                raise
            if not valid():
                bundle.close()
                bundle = None
                return
            retire = None
            with self._lifecycle_lock:
                if not valid():
                    bundle.close()
                    bundle = None
                    return
                commit_started = time.perf_counter()
                if bundle.commit is not None:
                    bundle.commit()
                self.vision, self.control = vision, control
                retire = bundle.retire
                self._rebuild_commit_timing.add((time.perf_counter() - commit_started) * 1000.0)
            if retire is not None:
                retire_started = time.perf_counter()
                try:
                    retire()
                except Exception:
                    _LOGGER.exception("step=follow_engine.rebuild_retire_failed")
                finally:
                    self._rebuild_retire_timing.add((time.perf_counter() - retire_started) * 1000.0)
            with self._lifecycle_lock:
                targets = list(self._target_cache.items())
                # Dynamic targets are normally owned by Control and therefore
                # do not pass through the parent target queue.  A replacement
                # worker still needs the latest leader position; take it from
                # the last fused snapshot before replaying cached targets.
                if self._control_owns_live_targets and self._live_target_source:
                    latest = self._last_snapshot
                    source_state = (
                        latest.roles.get(self._live_target_source)
                        if latest is not None else None
                    )
                    handover_target = getattr(source_state, "position_native", None)
                    if handover_target is not None:
                        normalized = (float(handover_target[0]), float(handover_target[1]))
                        self._live_target_last = normalized
                        targets.extend(
                            (role_id, normalized)
                            for role_id in self._live_target_roles
                            if role_id != self._live_target_source
                        )
            for role_id, target in targets:
                control.update_target(role_id, target)
            self._worker_state = {"vision": "running", "control": "running"}
            self._last_progress_monotonic = {"vision": time.monotonic(), "control": time.monotonic()}
            self._worker_ready = {"vision": False, "control": False}
            self._started_monotonic = time.monotonic()
            self._last_snapshot = None
            self._rebuild_count += 1
            self._last_error = f"worker_rebuilt:{reason}"
            _LOGGER.info("step=follow_engine.rebuild_completed reason=%s count=%s epoch=%s vision_id=%s control_id=%s", reason, self._rebuild_count, session_epoch, id(vision), id(control))
        except Exception as exc:
            if bundle is not None:
                bundle.close()
            with self._lifecycle_lock:
                current_session = self._session_epoch == session_epoch
            if current_session:
                self._last_error = f"worker_rebuild_failed: {type(exc).__name__}: {exc}"
                self._worker_state = {"vision": "error", "control": "error"}
                _LOGGER.exception("step=follow_engine.rebuild_failed")
        finally:
            self._rebuild_attempt_timing.add((time.perf_counter() - attempt_started) * 1000.0)
            with self._lifecycle_lock:
                if self._session_epoch == session_epoch:
                    self._rebuild_in_progress = False

    def _shutdown_rebuild_executor(self, *, wait_timeout: float = 0.25) -> None:
        """Cancel a rebuild and wait a bounded time for its worker to leave.

        ``ThreadPoolExecutor.shutdown(wait=False)`` only prevents queued work;
        it does not stop a future already running.  Clearing the future and
        immediately starting another session therefore allowed an old rebuild
        to overlap the new session.  Detach the executor under the lifecycle
        lock, then wait outside the lock so worker completion can still pass
        through ``valid()``.  A future that exceeds the bound remains isolated
        by its captured epoch/cancel token and is shut down without blocking
        the caller indefinitely.
        """
        with self._lifecycle_lock:
            self._rebuild_cancel.set()
            executor, self._rebuild_executor = self._rebuild_executor, None
            future, self._rebuild_future = self._rebuild_future, None
            self._rebuild_in_progress = False
        if future is not None and not future.done():
            try:
                future.result(timeout=max(0.0, float(wait_timeout)))
            except FutureTimeoutError:
                _LOGGER.warning("step=follow_engine.rebuild_shutdown_timeout")
                with self._lifecycle_lock:
                    self._retiring_rebuild_futures.add(future)
            except Exception:
                # Rebuild failures are already recorded by the worker when it
                # belongs to the current session; shutdown must still finish.
                pass
        if executor is not None:
            completed = future is None or future.done()
            executor.shutdown(wait=completed, cancel_futures=True)

    def _await_retiring_rebuilds(self, *, timeout: float) -> bool:
        """Wait for canceled futures before a session reuses worker handles."""
        deadline = time.monotonic() + max(0.0, float(timeout))
        while True:
            with self._lifecycle_lock:
                retiring = tuple(self._retiring_rebuild_futures)
            if not retiring:
                return True
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return False
            for future in retiring:
                try:
                    future.result(timeout=remaining)
                except FutureTimeoutError:
                    return False
                except Exception:
                    pass
                finally:
                    if future.done():
                        with self._lifecycle_lock:
                            self._retiring_rebuild_futures.discard(future)

    def _forward_execution_receipts(self) -> None:
        poll = getattr(self.output, "poll_receipts", None)
        send = getattr(self.control, "send_execution", None)
        if not callable(poll) or not callable(send):
            return
        try:
            receipts = tuple(poll())
        except Exception as exc:
            self._last_error = f"output_receipt_poll_failed: {type(exc).__name__}: {exc}"
            return
        for receipt in receipts:
            if isinstance(receipt, ExecutionReceipt):
                try:
                    send(receipt)
                except Exception as exc:
                    self._last_error = f"execution_feedback_send_failed: {type(exc).__name__}: {exc}"

    def _refresh_worker_liveness(self) -> None:
        """Surface silent child exits without converting them into user stop."""
        for name, handle in (("vision", self.vision), ("control", self.control)):
            process = getattr(handle, "process", None)
            if process is None:
                continue
            alive = getattr(process, "is_alive", None)
            if not callable(alive):
                continue
            try:
                running = bool(alive())
            except Exception as exc:
                self._worker_state[name] = "unknown"
                self._last_error = f"{name}_liveness_failed: {type(exc).__name__}: {exc}"
                continue
            if not running and self._worker_state.get(name) == "running":
                self._worker_state[name] = "exited"
                self._last_error = f"{name}_worker_exited_without_event"
                self._record_worker_fault(name, self._last_error)
                if name == "control":
                    self._neutralize_output()

    def _neutralize_output(self) -> None:
        neutralize = getattr(self.output, "neutralize", None)
        if not callable(neutralize):
            return
        try:
            neutralize()
        except Exception as exc:
            self._last_error = f"output_neutralize_failed: {type(exc).__name__}: {exc}"

    def snapshot(self) -> FusionSnapshot | None:
        return self._last_snapshot

    @property
    def latest_visual_observation(self) -> Any | None:
        """Return the most recent generation-valid vision observation.

        The returned DTO is immutable by contract and is used only as a
        handover seed during worker rebuild.  It is intentionally separate
        from :meth:`snapshot`, which is produced by the control worker.
        """

        with self._lifecycle_lock:
            return self._last_visual_observation

    def diagnostics(self) -> dict[str, object]:
        self._refresh_output_health()
        now = time.monotonic()
        return {
            "active": self._active,
            "generation": self.token.generation if self.token is not None else None,
            "map_instance": self.token.map_instance if self.token is not None else None,
            "last_error": self._last_error,
            "first_fault": dict(self._first_fault) if self._first_fault is not None else None,
            "worker_state": dict(self._worker_state),
            "worker_pids": {
                "vision": getattr(getattr(self.vision, "process", None), "pid", None),
                "control": getattr(getattr(self.control, "process", None), "pid", None),
            },
            "rebuild_count": self._rebuild_count,
            "rebuild_attempts": self._rebuild_attempts,
            "rebuild_in_progress": self._rebuild_in_progress,
            "rebuild_timing": {
                "attempt": self._rebuild_attempt_timing.as_dict("attempt_"),
                "commit": self._rebuild_commit_timing.as_dict("commit_"),
                "retire": self._rebuild_retire_timing.as_dict("retire_"),
            },
            "worker_stall_timeout_ms": self._stall_timeout_ms,
            "output_state": self._output_state,
            "output_diagnostics": dict(self._output_diagnostics),
            "relay_diagnostics": (
                self._relay.diagnostics() if self._relay is not None else None
            ),
            "parent_poll_count": self._parent_poll_count,
            "parent_poll_gap_ms": (
                None if self._last_parent_poll_monotonic <= 0
                else max(0.0, (now - self._last_parent_poll_monotonic) * 1000.0)
            ),
            "parent_entry_gap_ms": (
                None if self._last_parent_poll_monotonic <= 0
                else max(0.0, (now - self._last_parent_poll_monotonic) * 1000.0)
            ),
            "child_progress_age_ms": {
                name: (None if stamp <= 0 else max(0.0, (now - stamp) * 1000.0))
                for name, stamp in self._last_progress_monotonic.items()
            },
            "child_ready": dict(self._worker_ready),
            "last_parent_event": dict(self._last_parent_event),
            "ipc_evidence": {
                "vision_last_sequence": self._last_parent_event.get("vision"),
                "control_last_tick": self._last_parent_event.get("control"),
                "queue_age_is_parent_consumption_age": True,
            },
            "last_control_diagnostics": dict(self._last_control_diagnostics),
        }

    def _refresh_output_health(self) -> None:
        """Consume asynchronous output actor failures without blocking.

        ``AsyncSnapshotOutput.start`` returns before its adapter lease is
        acquired.  A failed acquisition is therefore a runtime start failure,
        not a successful engine start with a silent output.  Output adapters
        that do not expose diagnostics retain the synchronous behaviour.
        """
        diagnostics = getattr(self.output, "diagnostics", None)
        if not callable(diagnostics):
            return
        try:
            state = dict(diagnostics())
        except Exception as exc:
            self._output_state = "error"
            self._last_error = f"output_diagnostics_failed: {type(exc).__name__}: {exc}"
            return
        self._output_diagnostics = state
        actor_state = str(state.get("state", ""))
        if actor_state:
            self._output_state = actor_state
        elif state.get("started") is True:
            self._output_state = "running"
        failure = state.get("failure")
        if actor_state != "failed" and not failure:
            return
        if not self._active:
            return
        error = state.get("last_error") or "output actor failed"
        self._last_error = f"output_actor_start_failed: {error}"
        # A transport/Host lease failure is recoverable during a continuous
        # follow session.  Keep vision, prediction, target propagation and
        # recovery alive, neutralize output, and retry the actor with bounded
        # exponential backoff.  Only the explicit user stop releases the
        # session; this prevents a transient lease error from masquerading as
        # a follow completion.
        # Serialize restart against explicit stop and guard it with the
        # session epoch.  Without this, a health poll can start a new actor
        # after the user has already stopped the session, leaving a late Host
        # lease alive or writing into the next generation.
        with self._output_restart_lock:
            with self._lifecycle_lock:
                if not self._active:
                    return
                restart_epoch = self._session_epoch
            now = time.monotonic()
            if now < self._next_output_restart_monotonic:
                return
            self._output_restart_attempts += 1
            self._next_output_restart_monotonic = now + min(
                5.0, 0.25 * (2 ** min(self._output_restart_attempts - 1, 4))
            )
            try:
                self.output.start()
                with self._lifecycle_lock:
                    current = self._active and self._session_epoch == restart_epoch
                if not current:
                    self.output.stop(force=True)
                    return
                self._output_state = "restarting"
                if self._last_snapshot is not None:
                    self.output.apply(self._last_snapshot)
                _LOGGER.warning(
                    "step=follow_engine.output_actor_restart attempt=%s backoff_ms=%s epoch=%s",
                    self._output_restart_attempts,
                    int((self._next_output_restart_monotonic - now) * 1000),
                    restart_epoch,
                )
            except Exception as exc:
                self._output_state = "failed"
                self._last_error = f"output_actor_restart_failed: {type(exc).__name__}: {exc}"

    def _deactivate_after_output_failure(self) -> None:
        """Release process resources after an async output start failure."""
        if not self._active:
            return
        if self._relay is not None:
            self._relay.stop()
        with self._lifecycle_lock:
            self._active = False
            self._session_epoch += 1
            self._rebuild_cancel.set()
        for name, component in (("vision", self.vision), ("control", self.control)):
            try:
                component.stop()
            except Exception:
                _LOGGER.exception("step=follow_engine.output_failure_component_stop_failed component=%s", name)
        try:
            with self._output_restart_lock:
                self.output.stop(force=True)
        except Exception:
            _LOGGER.exception("step=follow_engine.output_failure_output_stop_failed")
        self._worker_state = {"vision": "stopped", "control": "stopped"}
        self.clock.stop()
        self.token = None
        self._target_cache.clear()
        self._last_visual_observation = None
        self._live_target_source = None
        self._live_target_roles = ()
        self._live_target_last = None
        self._live_target_last_capture_ms = None
        self._live_target_initial_position = None
        self._shutdown_rebuild_executor()

    def stop(self, *, reason: str = "user") -> None:
        _LOGGER.warning(
            "step=follow_engine.stop_begin reason=%s active=%s generation=%s output_state=%s worker_state=%s",
            reason, self._active,
            self.token.generation if self.token is not None else None,
            self._output_state, dict(self._worker_state),
        )
        with self._lifecycle_lock:
            was_active = self._active
            self._active = False
            self._session_epoch += 1
            self._rebuild_cancel.set()
        if self._relay is not None:
            self._relay.stop()
        if not was_active:
            self._last_visual_observation = None
            self._live_target_source = None
            self._live_target_roles = ()
            self._live_target_last = None
            self._live_target_last_capture_ms = None
            self._live_target_initial_position = None
            self._shutdown_rebuild_executor()
            return
        try:
            self.vision.stop()
        finally:
            try:
                self.control.stop()
            finally:
                try:
                    with self._output_restart_lock:
                        self.output.stop(force=True)
                finally:
                    # State cleanup must happen even if one adapter reports a
                    # stop failure; otherwise a later start is blocked by a
                    # stale active token and the page appears stuck.
                    self._active = False
                    self._output_state = "stopped"
                    self._worker_state = {"vision": "stopped", "control": "stopped"}
                    self.clock.stop()
                    self.token = None
                    self._last_error = "" if reason == "user" else str(reason)
                    self._last_visual_observation = None
                    self._target_cache.clear()
                    self._live_target_source = None
                    self._live_target_roles = ()
                    self._live_target_last = None
                    self._live_target_last_capture_ms = None
                    self._live_target_initial_position = None
                    self._shutdown_rebuild_executor()
                    _LOGGER.info(
                        "step=follow_engine.stop_finished reason=%s active=%s output_state=%s worker_state=%s",
                        reason, self._active, self._output_state, dict(self._worker_state),
                    )


__all__ = ["ControlPort", "FollowEnginePort", "FollowEngineStart", "OutputPort", "RebuildBundle", "VisionPort"]
