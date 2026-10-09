"""Bridge fusion snapshots to leased controller outputs.

The follow engine produces normalized :class:`OutputIntent` values while the
existing Host adapter exposes ``start/write/heartbeat/rearm/stop``.  This
module is the narrow boundary between those contracts.  It deliberately owns
no PoE2 policy: callers choose the role-to-controller factory and the set of
continuous roles, while :class:`OutputScheduler` owns lease heartbeats and
session rearming.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any, Callable
import time
import logging
from collections import deque
import threading

from ..contracts import FusionSnapshot
from ..execution_feedback import ExecutionReceipt
from .output_scheduler import OutputPort, OutputScheduler
from ..timing import TimingWindow
from ..diagnostic_events import DiagnosticJournal, DiagnosticRelay

_LOGGER = logging.getLogger("auto_modules.poe2_live_terrain.follow_engine")


class SnapshotOutputAdapter:
    """Adapt ``FusionSnapshot`` output intents to one scheduler per session.

    Outputs may be supplied eagerly for offline fakes, or created lazily from
    ``output_factory(role_id, controller)`` on the first snapshot.  Lazy
    creation keeps Host connections out of page construction and makes the
    real side effect happen only after the user explicitly starts follow.
    """

    def __init__(
        self,
        outputs: Mapping[str, OutputPort] | None = None,
        *,
        output_factory: Callable[[str, int], OutputPort] | None = None,
        continuous_roles: set[str] | frozenset[str] = (),
        heartbeat_interval_ms: int = 100,
        close_outputs: bool = True,
        arm_delay_ms: int = 0,
        clock_ms: Callable[[], int] | None = None,
    ) -> None:
        if outputs is not None and output_factory is not None:
            raise ValueError("outputs and output_factory are mutually exclusive")
        if outputs is None and output_factory is None:
            raise ValueError("outputs or output_factory is required")
        self._outputs = {str(role): output for role, output in (outputs or {}).items()}
        self._output_factory = output_factory
        self._continuous_roles = frozenset(str(role) for role in continuous_roles)
        self._heartbeat_interval_ms = int(heartbeat_interval_ms)
        self._close_outputs = bool(close_outputs)
        if int(arm_delay_ms) < 0:
            raise ValueError("arm_delay_ms must be non-negative")
        self._arm_delay_ms = int(arm_delay_ms)
        self._clock_ms = clock_ms or (lambda: int(time.monotonic() * 1000))
        self._arm_not_before_ms = 0
        self._last_gate_remaining_ms = 0
        self._scheduler: OutputScheduler | None = None
        self._started = False
        self._generation = 1
        self._receipt_sequence = 0
        self._receipts = deque(maxlen=64)
        self._receipt_lock = threading.Lock()
        self._apply_timing = TimingWindow(256)
        self._receipt_ages = TimingWindow(256)
        self._evidence = DiagnosticJournal()
        self._evidence_relay = DiagnosticRelay(_LOGGER)

    @property
    def started(self) -> bool:
        return self._started

    def start(self) -> None:
        if self._started:
            return
        self._scheduler = OutputScheduler(
            self._outputs,
            continuous_roles=self._continuous_roles,
            heartbeat_interval_ms=self._heartbeat_interval_ms,
            on_write=self._record_write,
        )
        self._scheduler.start()
        self._arm_not_before_ms = max(0, int(self._clock_ms())) + self._arm_delay_ms
        self._last_gate_remaining_ms = self._arm_delay_ms
        self._started = True
        _LOGGER.info("step=follow_engine.output_scheduler_started adapter_id=%s roles=%s arm_delay_ms=%s", id(self), tuple(self._outputs), self._arm_delay_ms)

    def apply(self, snapshot: FusionSnapshot) -> None:
        started = time.perf_counter()
        if not self._started:
            raise RuntimeError("snapshot output adapter is not started")
        # Keep the small offline adapter contract compatible with legacy test
        # snapshots that only expose session_active/output_intents; real
        # FusionSnapshot instances always carry a generation header.
        self._generation = int(getattr(snapshot, "generation", self._generation))
        remaining = max(0, self._arm_not_before_ms - int(self._clock_ms()))
        self._last_gate_remaining_ms = remaining
        if remaining > 0:
            # The control/vision workers continue running during the handoff
            # window.  Establish a neutral lease as soon as a role is known;
            # otherwise the first movement snapshot pays both the configured
            # focus handoff and the Host session startup latency.  ``prime``
            # never records movement execution feedback and is idempotent, so
            # the arm gate still suppresses all non-zero input.
            self._ensure_intent_outputs(snapshot)
            assert self._scheduler is not None
            self._scheduler.register_outputs(self._outputs)
            self._scheduler.prime_neutral(
                {str(intent.role_id) for intent in snapshot.output_intents}
            )
            self._apply_timing.add((time.perf_counter() - started) * 1000.0)
            return
        self._ensure_intent_outputs(snapshot)
        assert self._scheduler is not None
        self._scheduler.register_outputs(self._outputs)
        try:
            self._scheduler.apply(snapshot)
        except Exception:
            for intent in snapshot.output_intents:
                self._record_zero(intent.role_id)
            raise
        finally:
            self._apply_timing.add((time.perf_counter() - started) * 1000.0)

    def _record_write(self, intent, result) -> None:
        self._receipt_sequence += 1
        with self._receipt_lock:
            self._receipts.append(ExecutionReceipt(
                self._generation, self._receipt_sequence, intent.role_id,
                tuple(getattr(result, "effective_input_vector", intent.vector)),
                int(getattr(result, "accepted_at_ms", time.time() * 1000)),
                max(0, int(getattr(result, "ttl_ms", intent.duration_ms))),
                control_tick=intent.control_tick,
                target_revision=intent.target_revision,
                visual_sequence=intent.visual_sequence,
            ))
            receipt = self._receipts[-1]
            self._receipt_ages.add(max(0.0, time.time() * 1000.0 - float(getattr(result, "accepted_at_ms", time.time() * 1000.0))))
        self._evidence.record("output_receipt", intent.role_id, "neutral" if intent.neutral else "moving",
            controller=intent.controller, control_tick=receipt.control_tick,
            target_revision=receipt.target_revision, visual_sequence=receipt.visual_sequence,
            receipt_sequence=receipt.sequence, accepted_at_ms=receipt.accepted_at_ms,
            vector=receipt.vector, valid_for_ms=receipt.valid_for_ms,
            evidence="transport_only", backend_result_present=result is not None)
        self._evidence_relay.consume("output", self._generation, self._evidence.snapshot())

    def _record_zero(self, role_id: str) -> None:
        self._receipt_sequence += 1
        with self._receipt_lock:
            self._receipts.append(ExecutionReceipt(self._generation, self._receipt_sequence, role_id,
                                                   (0.0, 0.0), int(time.time() * 1000), 0))

    def poll_receipts(self) -> tuple[ExecutionReceipt, ...]:
        with self._receipt_lock:
            results = tuple(self._receipts)
            self._receipts.clear()
            return results

    def cancel_pending_io(self) -> None:
        """Interrupt dedicated Host clients without taking scheduler/port locks."""
        for output in tuple(self._outputs.values()):
            cancel = getattr(output, "cancel_pending_io", None)
            if callable(cancel):
                cancel()

    def stop(self, *, force: bool = True) -> None:
        _LOGGER.info("step=follow_engine.output_scheduler_stop_requested adapter_id=%s roles=%s force=%s", id(self), tuple(self._outputs), force)
        scheduler = self._scheduler
        self._scheduler = None
        self._started = False
        self._arm_not_before_ms = 0
        self._last_gate_remaining_ms = 0
        error = None
        try:
            if scheduler is not None:
                scheduler.stop(force=bool(force))
        except Exception as exc:
            error = exc
        try:
            if self._close_outputs:
                self._close_all_outputs()
        except Exception as exc:
            error = error or exc
        finally:
            self._outputs.clear()
        if error is not None:
            raise error
        _LOGGER.info("step=follow_engine.output_scheduler_stopped adapter_id=%s", id(self))

    def neutralize(self) -> None:
        """Neutralize active sticks without releasing the dynamic session."""
        if self._scheduler is not None:
            self._scheduler.neutralize()
            for role in tuple(self._outputs):
                self._record_zero(role)

    def diagnostics(self) -> dict[str, Any]:
        scheduler = self._scheduler
        result: dict[str, Any] = {
            "started": self._started,
            "roles": tuple(sorted(self._outputs)),
            "arm_delay_ms": self._arm_delay_ms,
            "arm_not_before_ms": self._arm_not_before_ms,
            "arm_gate_remaining_ms": self._last_gate_remaining_ms,
        }
        if scheduler is not None:
            result.update(scheduler.diagnostics())
        snapshots: dict[str, Any] = {}
        for role, output in self._outputs.items():
            reader = getattr(output, "snapshot", None)
            if callable(reader):
                try:
                    snapshots[role] = reader()
                except Exception as exc:  # diagnostics must not break polling
                    snapshots[role] = {"error": f"{type(exc).__name__}: {exc}"}
        result["outputs"] = snapshots
        result["apply_timing"] = self._apply_timing.as_dict("output_apply_")
        result["receipt_age"] = self._receipt_ages.as_dict("receipt_age_")
        return result

    def _ensure_intent_outputs(self, snapshot: FusionSnapshot) -> None:
        if self._output_factory is None:
            return
        for intent in snapshot.output_intents:
            role_id = str(intent.role_id)
            if role_id in self._outputs:
                continue
            output = self._output_factory(role_id, int(intent.controller))
            if output is None:
                raise RuntimeError(f"output factory returned no output for role {role_id}")
            self._outputs[role_id] = output

    def _close_all_outputs(self) -> None:
        first_error: Exception | None = None
        for output in tuple(self._outputs.values()):
            close = getattr(output, "close", None)
            if not callable(close):
                continue
            try:
                close()
            except Exception as exc:
                first_error = first_error or exc
        if first_error is not None:
            raise first_error


__all__ = ["SnapshotOutputAdapter"]
