"""Pure control runtime used by the future FollowControlProcess."""

from __future__ import annotations

import math
import multiprocessing as mp
import queue
import time
from dataclasses import dataclass
import traceback
from typing import Any, Callable, Mapping

from ..contracts import (
    FusionSnapshot,
    ObservationSource,
    OutputIntent,
    RoleFusedState,
    RoleVisualObservation,
    StageTiming,
    VisualObservation,
)
from ..generation import GenerationToken, SequenceGate
from ..recovery.global_recovery import GlobalRecoveryBackend
from ..recovery.local_recovery import LocalRecoveryBackend
from ..recovery.memory_recovery import MemoryRecoveryBackend
from ..recovery.recovery_policy import RecoveryObservation, RecoveryPolicy
from ..tracking.command_odometry import CommandOdometry
from ..tracking.position_fusion import fuse_observation
from ..tracking.tracking_state import RoleTrackingState
from .route_controller import RouteDecision, StraightLineRouteController


@dataclass
class _RoleControl:
    controller: int
    state: RoleTrackingState | None = None
    odometry: CommandOdometry | None = None
    target: tuple[float, float] | None = None
    last_vector: tuple[float, float] = (0.0, 0.0)
    last_duration_ms: int = 0
    misses: int = 0


class FollowControlRuntime:
    """Fuse the newest visual message with command odometry at control rate.

    This class is deliberately process-agnostic.  A spawned process wrapper can
    own it later; offline replay and unit tests can use it directly.
    """

    def __init__(
        self,
        token: GenerationToken,
        roles: Mapping[str, int],
        *,
        route_controller: StraightLineRouteController | None = None,
        recovery_policy: RecoveryPolicy | None = None,
        local_recovery: LocalRecoveryBackend | None = None,
        local_search: Callable[[object, tuple[float, float], float], Any] | None = None,
        memory_recovery: MemoryRecoveryBackend | None = None,
        global_recovery: GlobalRecoveryBackend | None = None,
    ) -> None:
        if not roles:
            raise ValueError("at least one control role is required")
        self.token = token
        self.gate = SequenceGate(token)
        self.route_controller = route_controller or StraightLineRouteController()
        self.recovery_policy = recovery_policy or RecoveryPolicy()
        self.local_recovery = local_recovery
        self.local_search = local_search
        self.memory_recovery = memory_recovery
        self.global_recovery = global_recovery
        self._roles = {str(role): _RoleControl(int(controller)) for role, controller in roles.items()}
        self._latest_visual: VisualObservation | None = None
        self._latest_frame: object | None = None
        self._last_local_sequence: dict[str, int] = {}
        self._last_evidence_at_ms: dict[str, int] = {}
        self._memory_succeeded_tick = False
        self._memory_failed_tick = False
        self._global_succeeded_tick = False
        self._global_failed_tick = False
        self._memory_elapsed_tick = 0.0
        self._global_elapsed_tick = 0.0
        self._host_session_expired = False
        self._map_instance_valid = True
        self._transform_valid = True
        self._last_tick_ms: int | None = None
        self._tick_sequence = 0
        self._session_active = True
        self._last_snapshot: FusionSnapshot | None = None

    @property
    def session_active(self) -> bool:
        return self._session_active

    def seed_position(self, role_id: str, position: tuple[float, float], *, captured_at_ms: int, uncertainty: float = 0.0) -> None:
        role = self._roles[str(role_id)]
        role.state = RoleTrackingState(str(role_id), position, (0.0, 0.0), uncertainty, captured_at_ms, captured_at_ms, "visual_seed")
        role.odometry = CommandOdometry(position, uncertainty=uncertainty, captured_at_ms=captured_at_ms)

    def update_target(self, role_id: str, target: tuple[float, float] | None) -> None:
        role = self._roles[str(role_id)]
        role.target = None if target is None else (float(target[0]), float(target[1]))

    def signal_recovery(self, kind: str) -> None:
        """Inject a transport/map boundary signal without stopping the session."""
        normalized = str(kind).strip().lower()
        if normalized == "host_session_expired":
            self._host_session_expired = True
        elif normalized == "map_changed":
            self._map_instance_valid = False
        elif normalized == "transform_invalid":
            self._transform_valid = False
        else:
            raise ValueError(f"unknown recovery signal: {kind}")

    def apply_visual(self, observation: VisualObservation, *, frame: object | None = None) -> bool:
        if not self.gate.accept(observation):
            return False
        self._latest_visual = observation
        self._latest_frame = observation if frame is None else frame
        for role_id, visual in observation.roles.items():
            if role_id not in self._roles or not visual.visible or visual.position_native is None:
                continue
            state = self._roles[role_id].state
            if state is None:
                self.seed_position(role_id, visual.position_native, captured_at_ms=observation.captured_at_ms, uncertainty=visual.uncertainty_native)
                self._last_evidence_at_ms[role_id] = int(observation.captured_at_ms)
                continue
            fused = fuse_observation(
                state.position_native,
                visual.position_native,
                prediction_sigma=max(1.0, state.uncertainty_native),
                observation_sigma=max(1.0, visual.uncertainty_native),
                max_innovation=max(20.0, state.uncertainty_native * 3.0 + 10.0),
                observation_confidence=visual.confidence,
            )
            if fused.accepted:
                self._roles[role_id].state = RoleTrackingState(
                    role_id,
                    fused.position,
                    visual.velocity_native,
                    fused.uncertainty,
                    observation.captured_at_ms,
                    observation.captured_at_ms,
                    "visual_fused",
                )
                self._roles[role_id].odometry = CommandOdometry(
                    fused.position,
                    uncertainty=fused.uncertainty,
                    captured_at_ms=observation.captured_at_ms,
                )
                self._roles[role_id].misses = 0
                self._last_evidence_at_ms[role_id] = int(observation.captured_at_ms)
            else:
                self._roles[role_id].misses += 1
        return True

    def _apply_recovery_positions(self, positions: Mapping[str, Any], *, now_ms: int, source: str) -> bool:
        applied = False
        for raw_role_id, point in positions.items():
            role_id = str(raw_role_id)
            if role_id not in self._roles or point is None:
                continue
            values = tuple(float(value) for value in point)
            if len(values) != 2 or not all(math.isfinite(value) for value in values):
                continue
            role = self._roles[role_id]
            uncertainty = max(1.0, role.state.uncertainty_native * 0.5) if role.state is not None else 2.0
            last_visual = role.state.last_visual_at_ms if role.state is not None else None
            role.state = RoleTrackingState(role_id, values, (0.0, 0.0), uncertainty, last_visual, int(now_ms), source)
            role.odometry = CommandOdometry(values, uncertainty=uncertainty, captured_at_ms=int(now_ms))
            role.misses = 0
            self._last_evidence_at_ms[role_id] = int(now_ms)
            applied = True
        return applied

    def _poll_recovery_backends(self, *, now_ms: int) -> float:
        started = time.perf_counter()
        self._memory_succeeded_tick = self._memory_failed_tick = False
        self._global_succeeded_tick = self._global_failed_tick = False
        self._memory_elapsed_tick = self._global_elapsed_tick = 0.0
        if self.memory_recovery is not None:
            result = self.memory_recovery.poll(self.token)
            if result is not None:
                self._memory_elapsed_tick = float(result.elapsed_ms)
                if result.error:
                    self._memory_failed_tick = True
                else:
                    self._memory_succeeded_tick = self._apply_recovery_positions(
                        result.positions, now_ms=now_ms, source="memory_reanchor"
                    )
        if self.global_recovery is not None:
            result = self.global_recovery.poll(self.token)
            if result is not None:
                self._global_elapsed_tick = float(result.elapsed_ms)
                if result.error:
                    self._global_failed_tick = True
                else:
                    value = result.value
                    positions = getattr(value, "positions", value)
                    if isinstance(positions, Mapping):
                        self._global_succeeded_tick = self._apply_recovery_positions(
                            positions, now_ms=now_ms, source="global_reanchor"
                        )
        return (time.perf_counter() - started) * 1000.0

    def _run_local_recovery(self, role_id: str, *, now_ms: int) -> tuple[bool, float]:
        if self.local_recovery is None or self.local_search is None or self._latest_frame is None:
            return False, 0.0
        role = self._roles[role_id]
        if role.state is None:
            return False, 0.0
        started = time.perf_counter()
        result = self.local_recovery.match(self._latest_frame, role.state.position_native, self.local_search)
        elapsed = (time.perf_counter() - started) * 1000.0
        if not result.valid or result.position_native is None:
            return False, elapsed
        return self._apply_recovery_positions({role_id: result.position_native}, now_ms=now_ms, source="local_roi"), elapsed

    def _submit_memory_recovery(self, *, now_ms: int) -> bool:
        if self.memory_recovery is None or self.memory_recovery.in_flight or not self.memory_recovery.cooldown_ready(now_ms=now_ms):
            return False
        return self.memory_recovery.submit(self.token, now_ms=now_ms)

    def _memory_cooldown_ready(self, *, now_ms: int) -> bool:
        return bool(self.memory_recovery and not self.memory_recovery.in_flight and self.memory_recovery.cooldown_ready(now_ms=now_ms))

    def _submit_global_recovery(self) -> bool:
        if self.global_recovery is None or self.global_recovery.in_flight:
            return False
        return self.global_recovery.submit(self.token)

    def tick(self, *, now_ms: int) -> FusionSnapshot:
        started = time.perf_counter()
        now = int(now_ms)
        if now < 0:
            raise ValueError("now_ms must be non-negative")
        self._tick_sequence += 1
        recovery_poll_ms = self._poll_recovery_backends(now_ms=now)
        visual = self._latest_visual
        roles: dict[str, RoleFusedState] = {}
        vectors: dict[str, tuple[float, float]] = {}
        intents: list[OutputIntent] = []
        route_points: list[tuple[float, float]] = []
        decisions = []
        local_ms = 0.0
        prediction_ms = 0.0
        route_ms = 0.0
        memory_requested = False
        global_requested = False
        for role_id, control in self._roles.items():
            if control.state is None:
                continue
            if control.odometry is not None and self._last_tick_ms is not None and control.last_duration_ms > 0:
                prediction_started = time.perf_counter()
                elapsed = max(0, now - self._last_tick_ms)
                if elapsed > 0 and control.last_vector != (0.0, 0.0):
                    estimate = control.odometry.step(
                        control.last_vector,
                        self.route_controller.magnitude * 100.0,
                        min(elapsed, control.last_duration_ms),
                        now_ms=now,
                        speed_error_units_per_second=20.0,
                        timing_error_ms=10.0,
                    )
                    control.state = RoleTrackingState(
                        role_id,
                        estimate.position,
                        estimate.velocity,
                        estimate.uncertainty,
                        control.state.last_visual_at_ms,
                        now,
                        "command_prediction",
                    )
                prediction_ms += (time.perf_counter() - prediction_started) * 1000.0
            visual_item: RoleVisualObservation | None = visual.roles.get(role_id) if visual is not None else None
            evidence_at = self._last_evidence_at_ms.get(role_id, control.state.last_visual_at_ms)
            age = float("inf") if evidence_at is None else max(0.0, now - evidence_at)
            visible = bool(visual_item and visual_item.visible and visual_item.position_native is not None and age <= 600.0)
            if visible:
                control.misses = 0
            else:
                control.misses += 1
            local_attempted = bool(visual is not None and self._last_local_sequence.get(role_id) == visual.sequence)
            decision = self.recovery_policy.decide(
                RecoveryObservation(
                    frame_available=visual is not None,
                    frame_age_ms=age if math.isfinite(age) else None,
                    visual_match=visible,
                    local_attempted=local_attempted,
                    memory_in_flight=bool(self.memory_recovery and self.memory_recovery.in_flight),
                    memory_cooldown_ready=self._memory_cooldown_ready(now_ms=now),
                    memory_succeeded=self._memory_succeeded_tick,
                    memory_failed=self._memory_failed_tick,
                    global_in_flight=bool(self.global_recovery and self.global_recovery.in_flight),
                    global_succeeded=self._global_succeeded_tick,
                    global_failed=self._global_failed_tick,
                    host_session_expired=self._host_session_expired,
                    map_instance_valid=self._map_instance_valid,
                    transform_valid=self._transform_valid,
                    consecutive_misses=control.misses,
                    prediction_uncertainty=control.state.uncertainty_native,
                )
            )
            if decision.action.value == "local_retry" and visual is not None:
                self._last_local_sequence[role_id] = visual.sequence
                local_succeeded, elapsed_ms = self._run_local_recovery(role_id, now_ms=now)
                local_ms += elapsed_ms
                if local_succeeded:
                    control.state = self._roles[role_id].state
                    age = 0.0
                decision = self.recovery_policy.decide(
                    RecoveryObservation(
                        frame_available=True,
                        frame_age_ms=age if math.isfinite(age) else None,
                        visual_match=visible or local_succeeded,
                        local_attempted=True,
                        local_succeeded=local_succeeded,
                        memory_in_flight=bool(self.memory_recovery and self.memory_recovery.in_flight),
                        memory_cooldown_ready=self._memory_cooldown_ready(now_ms=now),
                        memory_succeeded=self._memory_succeeded_tick,
                        memory_failed=self._memory_failed_tick,
                        global_in_flight=bool(self.global_recovery and self.global_recovery.in_flight),
                        global_succeeded=self._global_succeeded_tick,
                        global_failed=self._global_failed_tick,
                        host_session_expired=self._host_session_expired,
                        map_instance_valid=self._map_instance_valid,
                        transform_valid=self._transform_valid,
                        consecutive_misses=control.misses,
                        prediction_uncertainty=control.state.uncertainty_native,
                    )
                )
            if decision.action.value == "memory_reanchor" and not memory_requested:
                memory_requested = self._submit_memory_recovery(now_ms=now)
            elif decision.action.value == "global_reanchor" and not global_requested:
                global_requested = self._submit_global_recovery()
            decisions.append(decision)
            route: RouteDecision | None = None
            if control.target is not None:
                route_started = time.perf_counter()
                route = self.route_controller.plan(control.state.position_native, control.target)
                route_ms += (time.perf_counter() - route_started) * 1000.0
                route_points.extend(route.route)
            if route is None or route.arrived:
                vector = (0.0, 0.0)
                duration = 0
            else:
                vector = route.vector
                duration = route.duration_ms
            control.last_vector = vector
            control.last_duration_ms = duration
            vectors[role_id] = vector
            roles[role_id] = RoleFusedState(
                role_id,
                control.state.position_native,
                control.state.velocity_native,
                control.state.uncertainty_native,
                control.state.source,
                age if math.isfinite(age) else 1e9,
            )
            intents.append(OutputIntent(role_id, control.controller, vector, duration, neutral=vector == (0.0, 0.0)))
        self._last_tick_ms = now
        self._host_session_expired = False
        self._map_instance_valid = True
        self._transform_valid = True
        active_decisions = [decision for decision in decisions if decision.keep_session]
        chosen = max(active_decisions, key=lambda decision: int(decision.level), default=None)
        state = chosen.state.value if chosen is not None else "follow_hold"
        reason = chosen.reason if chosen is not None else "no_roles_ready"
        total_ms = (time.perf_counter() - started) * 1000.0
        snapshot = FusionSnapshot(
            generation=self.token.generation,
            created_at_ms=now,
            roles=roles,
            recovery_state=state,
            recovery_reason=reason,
            route=tuple(route_points),
            control_vectors=vectors,
            output_intents=tuple(intents),
            session_active=self._session_active,
            timing=StageTiming(
                local_ms=local_ms,
                prediction_ms=prediction_ms,
                recovery_ms=recovery_poll_ms + local_ms,
                memory_ms=self._memory_elapsed_tick,
                global_ms=self._global_elapsed_tick,
                route_ms=route_ms,
                fusion_ms=total_ms,
                total_ms=total_ms,
            ),
        )
        self._last_snapshot = snapshot
        return snapshot

    def stop(self) -> None:
        self._session_active = False

    def snapshot(self) -> FusionSnapshot | None:
        return self._last_snapshot


@dataclass(frozen=True, slots=True)
class ControlProcessEvent:
    kind: str
    snapshot: FusionSnapshot | None = None
    error: str = ""
    traceback_text: str = ""


def _put_latest(output_queue, event: ControlProcessEvent) -> None:
    try:
        while True:
            output_queue.get_nowait()
    except queue.Empty:
        pass
    try:
        output_queue.put_nowait(event)
    except queue.Full:
        pass


def control_process_entry(
    roles: Mapping[str, int],
    generation: int,
    map_instance: str,
    command_queue,
    output_queue,
    stop_event,
    interval_ms: int,
    runtime_factory: Callable[[GenerationToken, Mapping[str, int]], FollowControlRuntime] | None = None,
) -> None:
    token = GenerationToken(int(generation), str(map_instance))
    # The default remains the pure offline runtime.  A caller that has a
    # spawn-safe composition (for example one with a warm memory backend and
    # a bounded local search) can inject it without making this process know
    # about Qt, PoE2 or Host adapters.
    runtime = (
        runtime_factory(token, roles)
        if runtime_factory is not None
        else FollowControlRuntime(token, roles)
    )
    if not isinstance(runtime, FollowControlRuntime):
        raise TypeError("runtime_factory must return FollowControlRuntime")
    try:
        while not stop_event.is_set():
            should_stop = False
            while True:
                try:
                    command = command_queue.get_nowait()
                except queue.Empty:
                    break
                kind = str(command.get("kind", ""))
                if kind == "visual":
                    runtime.apply_visual(command["observation"])
                elif kind == "target":
                    runtime.update_target(command["role_id"], command.get("target"))
                elif kind == "recovery_signal":
                    runtime.signal_recovery(command["signal"])
                elif kind == "stop":
                    runtime.stop()
                    should_stop = True
            if should_stop:
                break
            snapshot = runtime.tick(now_ms=int(time.time() * 1000))
            _put_latest(output_queue, ControlProcessEvent("snapshot", snapshot=snapshot))
            stop_event.wait(max(0.001, int(interval_ms) / 1000.0))
    except BaseException as exc:  # pragma: no cover - exercised in spawned process
        _put_latest(
            output_queue,
            ControlProcessEvent("error", error=f"{type(exc).__name__}: {exc}", traceback_text=traceback.format_exc()),
        )
    finally:
        _put_latest(output_queue, ControlProcessEvent("stopped"))


class FollowControlProcessHandle:
    """Parent-side lifecycle wrapper for the control process."""

    def __init__(
        self,
        roles: Mapping[str, int],
        *,
        interval_ms: int = 33,
        context: mp.context.BaseContext | None = None,
        runtime_factory: Callable[[GenerationToken, Mapping[str, int]], FollowControlRuntime] | None = None,
    ) -> None:
        if int(interval_ms) < 1:
            raise ValueError("interval_ms must be positive")
        self.roles = dict(roles)
        self.interval_ms = int(interval_ms)
        self.runtime_factory = runtime_factory
        self.context = context or mp.get_context("spawn")
        self.stop_event = self.context.Event()
        self.commands = self.context.Queue(maxsize=16)
        self.events = self.context.Queue(maxsize=1)
        self.process = None

    def start(self, *, generation: int, map_instance: str) -> None:
        if self.process is not None and self.process.is_alive():
            raise RuntimeError("control process is already running")
        self.stop_event.clear()
        self.process = self.context.Process(
            target=control_process_entry,
            args=(
                self.roles, int(generation), str(map_instance), self.commands,
                self.events, self.stop_event, self.interval_ms, self.runtime_factory,
            ),
            name=f"poe2-follow-control-{generation}",
            daemon=True,
        )
        self.process.start()

    def send_visual(self, observation: VisualObservation) -> None:
        self._send({"kind": "visual", "observation": observation})

    def update_target(self, role_id: str, target: tuple[float, float] | None) -> None:
        self._send({"kind": "target", "role_id": str(role_id), "target": target})

    def send_recovery_signal(self, signal: str) -> None:
        self._send({"kind": "recovery_signal", "signal": str(signal)})

    def poll_latest(self) -> ControlProcessEvent | None:
        latest = None
        while True:
            try:
                latest = self.events.get_nowait()
            except queue.Empty:
                return latest

    def stop(self, *, timeout: float = 2.0) -> None:
        try:
            self._send({"kind": "stop"})
        except Exception:
            pass
        self.stop_event.set()
        process = self.process
        if process is None:
            return
        process.join(timeout=max(0.0, float(timeout)))
        if process.is_alive():
            process.terminate()
            process.join(timeout=1.0)
        self.process = None

    def _send(self, command: dict) -> None:
        try:
            self.commands.put_nowait(command)
        except queue.Full:
            try:
                self.commands.get_nowait()
            except queue.Empty:
                pass
            self.commands.put_nowait(command)


__all__ = ["ControlProcessEvent", "FollowControlProcessHandle", "FollowControlRuntime", "control_process_entry"]
