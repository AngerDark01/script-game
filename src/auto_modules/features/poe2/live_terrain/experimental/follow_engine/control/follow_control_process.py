"""Pure control runtime used by the future FollowControlProcess."""

from __future__ import annotations

import math
import multiprocessing as mp
import queue
import time
from dataclasses import dataclass
import traceback
from typing import Mapping

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
    ) -> None:
        if not roles:
            raise ValueError("at least one control role is required")
        self.token = token
        self.gate = SequenceGate(token)
        self.route_controller = route_controller or StraightLineRouteController()
        self.recovery_policy = recovery_policy or RecoveryPolicy()
        self._roles = {str(role): _RoleControl(int(controller)) for role, controller in roles.items()}
        self._latest_visual: VisualObservation | None = None
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

    def apply_visual(self, observation: VisualObservation) -> bool:
        if not self.gate.accept(observation):
            return False
        self._latest_visual = observation
        for role_id, visual in observation.roles.items():
            if role_id not in self._roles or not visual.visible or visual.position_native is None:
                continue
            state = self._roles[role_id].state
            if state is None:
                self.seed_position(role_id, visual.position_native, captured_at_ms=observation.captured_at_ms, uncertainty=visual.uncertainty_native)
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
            else:
                self._roles[role_id].misses += 1
        return True

    def tick(self, *, now_ms: int) -> FusionSnapshot:
        started = time.perf_counter()
        now = int(now_ms)
        if now < 0:
            raise ValueError("now_ms must be non-negative")
        self._tick_sequence += 1
        visual = self._latest_visual
        roles: dict[str, RoleFusedState] = {}
        vectors: dict[str, tuple[float, float]] = {}
        intents: list[OutputIntent] = []
        route_points: list[tuple[float, float]] = []
        decisions = []
        for role_id, control in self._roles.items():
            if control.state is None:
                continue
            if control.odometry is not None and self._last_tick_ms is not None and control.last_duration_ms > 0:
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
            visual_item: RoleVisualObservation | None = visual.roles.get(role_id) if visual is not None else None
            age = float("inf") if control.state.last_visual_at_ms is None else max(0.0, now - control.state.last_visual_at_ms)
            visible = bool(visual_item and visual_item.visible and visual_item.position_native is not None and age <= 600.0)
            if visible:
                control.misses = 0
            else:
                control.misses += 1
            decision = self.recovery_policy.decide(
                RecoveryObservation(
                    frame_available=visual is not None,
                    frame_age_ms=age if math.isfinite(age) else None,
                    visual_match=visible,
                    consecutive_misses=control.misses,
                    prediction_uncertainty=control.state.uncertainty_native,
                )
            )
            decisions.append(decision)
            route: RouteDecision | None = None
            if control.target is not None:
                route = self.route_controller.plan(control.state.position_native, control.target)
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
            timing=StageTiming(fusion_ms=total_ms, total_ms=total_ms),
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
) -> None:
    runtime = FollowControlRuntime(
        GenerationToken(int(generation), str(map_instance)),
        roles,
    )
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
    ) -> None:
        if int(interval_ms) < 1:
            raise ValueError("interval_ms must be positive")
        self.roles = dict(roles)
        self.interval_ms = int(interval_ms)
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
            args=(self.roles, int(generation), str(map_instance), self.commands, self.events, self.stop_event, self.interval_ms),
            name=f"poe2-follow-control-{generation}",
            daemon=True,
        )
        self.process.start()

    def send_visual(self, observation: VisualObservation) -> None:
        self._send({"kind": "visual", "observation": observation})

    def update_target(self, role_id: str, target: tuple[float, float] | None) -> None:
        self._send({"kind": "target", "role_id": str(role_id), "target": target})

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
