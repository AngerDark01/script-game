"""Pure control runtime used by the future FollowControlProcess."""

from __future__ import annotations

import math
import copy
import multiprocessing as mp
import queue
import logging
import time
from dataclasses import dataclass, field, replace
import traceback
from collections import deque
from typing import Any, Callable, Mapping, Sequence

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
from ..execution_feedback import ExecutionReceipt
from ..recovery.global_recovery import GlobalRecoveryBackend
from ..recovery.local_recovery import LocalRecoveryBackend
from ..recovery.memory_recovery import MemoryRecoveryBackend
from ..recovery.recovery_policy import RecoveryObservation, RecoveryPolicy
from ..shared_frame_ring import SharedFrameRing
from ..worker_lifecycle import stop_process, close_queues
from ..tracking.command_odometry import CommandOdometry
from ..tracking.position_fusion import fuse_observation
from ..tracking.tracking_state import RoleTrackingState
from ..tracking.velocity_calibrator import VelocityCalibrator
from .route_controller import RouteController, RouteDecision, StraightLineRouteController
from ..timing import TimingWindow
from ..diagnostic_events import DiagnosticJournal


_LOGGER = logging.getLogger("auto_modules.poe2_live_terrain.follow_engine")


def _cadence_wait_seconds(*, started: float, interval_ms: int, now: float | None = None) -> float:
    """Return the remaining time in a start-to-start control cadence.

    A control tick may include fusion, recovery and route planning. Waiting a
    second full interval after that work turns a configured 30 FPS loop into
    ``tick_cost + interval`` and makes target-follow output visibly stale.
    Keep the same cadence contract as the vision worker and yield briefly when
    the tick is already late.
    """

    current = time.perf_counter() if now is None else float(now)
    remaining = float(started) + max(1, int(interval_ms)) / 1000.0 - current
    return max(0.001, remaining)


@dataclass
class _RoleControl:
    controller: int | None
    state: RoleTrackingState | None = None
    odometry: CommandOdometry | None = None
    target: tuple[float, float] | None = None
    target_revision: int = 0
    last_vector: tuple[float, float] = (0.0, 0.0)
    last_duration_ms: int = 0
    misses: int = 0
    execution_receipts: list[ExecutionReceipt] = field(default_factory=list)
    execution_cursor_ms: int = 0
    speed_calibrator: VelocityCalibrator | None = None
    last_visual_position: tuple[float, float] | None = None
    last_visual_at_ms: int | None = None


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
        route_controller: RouteController | None = None,
        recovery_policy: RecoveryPolicy | None = None,
        local_recovery: LocalRecoveryBackend | None = None,
        local_search: Callable[[object, tuple[float, float], float], Any] | Mapping[str, Callable[[object, tuple[float, float], float], Any]] | None = None,
        memory_recovery: MemoryRecoveryBackend | None = None,
        global_recovery: GlobalRecoveryBackend | None = None,
        frame_ring: SharedFrameRing | None = None,
        observation_role_ids: Mapping[str, int] | tuple[str, ...] | list[str] | None = None,
        live_target_source: str | None = None,
        live_target_roles: Sequence[str] = (),
        live_target_initial_position: tuple[float, float] | None = None,
    ) -> None:
        if not roles:
            raise ValueError("at least one control role is required")
        self.token = token
        self._evidence = DiagnosticJournal(capacity=48)
        self.gate = SequenceGate(token)
        self.route_controller = route_controller or StraightLineRouteController()
        self.recovery_policy = recovery_policy or RecoveryPolicy()
        self.local_recovery = local_recovery
        self.local_search = local_search
        self.memory_recovery = memory_recovery
        self.global_recovery = global_recovery
        self._frame_ring = frame_ring
        controlled = {str(role): int(controller) for role, controller in roles.items()}
        observed = tuple(
            str(role)
            for role in (observation_role_ids if observation_role_ids is not None else controlled)
        )
        if not observed or not set(controlled).issubset(observed):
            raise ValueError("observation roles must include every controlled role")
        source = None if live_target_source is None else str(live_target_source).strip()
        target_roles = tuple(str(role).strip() for role in live_target_roles if str(role).strip())
        if source is not None and source not in observed:
            raise ValueError("live target source must be an observation role")
        if any(role not in observed for role in target_roles):
            raise ValueError("live target roles must be observation roles")
        initial_target = None
        if live_target_initial_position is not None:
            initial_target = (float(live_target_initial_position[0]), float(live_target_initial_position[1]))
            if not all(math.isfinite(value) for value in initial_target):
                raise ValueError("live target initial position must be finite")
        self._roles = {
            role: _RoleControl(
                controlled.get(role),
                speed_calibrator=VelocityCalibrator(
                    initial_speed=max(1.0, float(getattr(self.route_controller, "magnitude", 0.65)) * 100.0),
                ),
            )
            for role in observed
        }
        # Map-aware planners cache a route.  Give each concurrently controlled
        # role its own cache so P1 and P2 cannot overwrite one another's
        # corridor on the same tick; retain the injected object for the
        # single-role/offline compatibility contract.
        self._route_controllers = {
            role: (self.route_controller if len(observed) == 1 else copy.deepcopy(self.route_controller))
            for role in observed
        }
        self._latest_visual: VisualObservation | None = None
        self._latest_frame: object | None = None
        self._last_local_sequence: dict[str, int] = {}
        # A visible marker is not evidence until the fusion gate accepts it.
        # Keep this separate from VisualObservation.roles so a rejected
        # candidate cannot refresh the role's health clock.
        self._last_accepted_visual_sequence: dict[str, int] = {}
        self._last_evidence_at_ms: dict[str, int] = {}
        self._memory_succeeded_tick = False
        self._memory_failed_tick = False
        self._memory_succeeded_roles: set[str] = set()
        self._global_succeeded_tick = False
        self._global_failed_tick = False
        self._global_succeeded_roles: set[str] = set()
        self._memory_elapsed_tick = 0.0
        self._global_elapsed_tick = 0.0
        self._host_session_expired = False
        self._map_instance_valid = True
        self._transform_valid = True
        self._last_tick_ms: int | None = None
        self._tick_sequence = 0
        self._session_active = True
        self._last_snapshot: FusionSnapshot | None = None
        self._tick_timing = TimingWindow(256)
        self._recovery_chain_timing = TimingWindow(256)
        self._local_recovery_timing = TimingWindow(256)
        self._memory_recovery_timing = TimingWindow(256)
        self._global_recovery_timing = TimingWindow(256)
        self._last_tick_started_monotonic = 0.0
        self._queue_age_ms = 0.0
        self._queue_depth = 0
        self._last_execution_sequence = 0
        # Bounded, process-safe explanation of the latest control decision.
        # This is deliberately a DTO of scalars/tuples only: it crosses the
        # Windows spawn queue and is sampled by the parent at low frequency.
        self._last_control_diagnostics: dict[str, object] = {}
        self._local_recovery_turn = 0
        # Dynamic target propagation belongs to the control process.  The
        # visual observation and its fused source position are already here;
        # routing this state back through the UI process adds a timer-sized
        # delay and permits a stale parent target to overwrite a fresh frame.
        self._live_target_source = source if target_roles else None
        self._live_target_roles = target_roles if source else ()
        self._live_target_initial_position = initial_target
        if initial_target is not None:
            for role_id in self._live_target_roles:
                self._roles[role_id].target = initial_target

    def attach_frame_ring(self, frame_ring: SharedFrameRing | None) -> None:
        """Attach the session's shared frame source without changing control state."""
        if frame_ring is not None and frame_ring.spec.map_instance != self.token.map_instance:
            raise ValueError("frame ring map instance does not match control session")
        self._frame_ring = frame_ring

    def _resolve_frame(self, observation: VisualObservation, frame: object | None) -> object | None:
        if frame is not None:
            if hasattr(frame, "sequence") and (
                frame.sequence != observation.sequence
                or frame.generation != observation.generation
                or frame.map_instance != observation.map_instance
                or frame.captured_at_ms != observation.captured_at_ms
            ):
                return None
            return frame
        if self._frame_ring is not None:
            sequence = int(observation.sequence)
            record = self._frame_ring.read(sequence)
            if (
                record is not None
                and record.generation == self.token.generation
                and record.map_instance == self.token.map_instance
                and record.captured_at_ms == observation.captured_at_ms
            ):
                return record
            # A newer image has a different camera transform.  Await its
            # observation instead of combining it with this frame's metadata.
            return None
        # Preserve the old injected-adapter contract when no shared source is
        # configured.  Such a placeholder is never mistaken for a ring frame.
        return observation

    @property
    def session_active(self) -> bool:
        return self._session_active

    def seed_position(self, role_id: str, position: tuple[float, float], *, captured_at_ms: int, uncertainty: float = 0.0) -> None:
        role = self._roles[str(role_id)]
        role.state = RoleTrackingState(str(role_id), position, (0.0, 0.0), uncertainty, captured_at_ms, captured_at_ms, "visual_seed")
        role.odometry = CommandOdometry(position, uncertainty=uncertainty, captured_at_ms=captured_at_ms)
        role.execution_cursor_ms = int(captured_at_ms)
        role.last_visual_position = (float(position[0]), float(position[1]))
        role.last_visual_at_ms = int(captured_at_ms)

    def record_execution(self, receipt: ExecutionReceipt) -> bool:
        """Accept one successful output write as odometry evidence.

        A receipt means that the controller transport accepted a pulse; it is
        deliberately not treated as proof that the game moved.  Generation
        and global sequence checks make late/duplicate feedback harmless.
        """
        if not isinstance(receipt, ExecutionReceipt):
            return False
        if receipt.generation != self.token.generation or receipt.role_id not in self._roles:
            return False
        if receipt.sequence <= self._last_execution_sequence:
            return False
        self._last_execution_sequence = receipt.sequence
        role = self._roles[receipt.role_id]
        if receipt.vector == (0.0, 0.0):
            # A neutral write supersedes overlapping active leases from the
            # same role; otherwise a late old pulse could keep odometry moving
            # after the output has already been neutralized.
            cutoff = int(receipt.accepted_at_ms)
            role.execution_receipts = [
                replace(item, valid_for_ms=max(0, cutoff - int(item.accepted_at_ms)))
                if int(item.accepted_at_ms) < cutoff < int(item.accepted_at_ms) + int(item.valid_for_ms)
                else item
                for item in role.execution_receipts
            ]
        role.execution_receipts.append(receipt)
        self._evidence.record("receipt_consumed", receipt.role_id, "neutral" if receipt.vector == (0, 0) else "moving",
            receipt_sequence=receipt.sequence, control_tick=receipt.control_tick,
            target_revision=receipt.target_revision, visual_sequence=receipt.visual_sequence,
            vector=receipt.vector, accepted_at_ms=receipt.accepted_at_ms, valid_for_ms=receipt.valid_for_ms)
        if len(role.execution_receipts) > 64:
            del role.execution_receipts[:-64]
        return True

    def update_target(self, role_id: str, target: tuple[float, float] | None) -> None:
        role = self._roles[str(role_id)]
        point = None if target is None else (float(target[0]), float(target[1]))
        if point != role.target:
            role.target_revision += 1
        role.target = point
        self._evidence.record("target", str(role_id), "cleared" if point is None else "updated",
            target=point, target_revision=role.target_revision, control_tick=self._tick_sequence,
            visual_sequence=None if self._latest_visual is None else self._latest_visual.sequence)

    @property
    def owns_live_target_policy(self) -> bool:
        """Whether observation-to-target propagation is local to this runtime."""
        return self._live_target_source is not None and bool(self._live_target_roles)

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

    def signal_execution_gap(self, role_id: str, *, sequence: int) -> None:
        """Record missing transport evidence without stopping the session."""
        role = self._roles.get(str(role_id))
        if role is None or role.state is None or int(sequence) < 1:
            _LOGGER.error("step=follow_engine.execution_gap_rejected role=%s sequence=%s", role_id, sequence)
            return
        role.misses += 1
        role.state = RoleTrackingState(
            role.state.role_id,
            role.state.position_native,
            role.state.velocity_native,
            role.state.uncertainty_native + 5.0,
            role.state.last_visual_at_ms,
            role.state.updated_at_ms,
            "execution_gap",
        )

    def apply_visual(self, observation: VisualObservation, *, frame: object | None = None) -> bool:
        if not self.gate.accept(observation):
            return False
        self._latest_visual = observation
        self._latest_frame = self._resolve_frame(observation, frame)
        searches = (
            tuple(self.local_search.values())
            if isinstance(self.local_search, Mapping)
            else (self.local_search,)
        )
        bound = set()
        for search in searches:
            if search is None or id(search) in bound:
                continue
            bound.add(id(search))
            bind_observation = getattr(search, "bind_observation", None)
            if callable(bind_observation):
                bind_observation(observation)
        accepted_positions: dict[str, tuple[float, float]] = {}
        for role_id, visual in observation.roles.items():
            if role_id not in self._roles or not visual.visible or visual.position_native is None:
                continue
            role = self._roles[role_id]
            state = role.state
            confirmed = role_id in observation.association_diagnostics.get("confirmed_roles", ()) and visual.confidence >= 0.85
            if confirmed and state is not None:
                self._apply_recovery_positions({role_id: visual.position_native},
                    now_ms=observation.captured_at_ms, source="visual_confirmed")
                self._last_accepted_visual_sequence[role_id] = observation.sequence
                # Do not train speed from an anchor correction jump.
                accepted_positions[role_id] = visual.position_native
                continue
            if state is None:
                self.seed_position(role_id, visual.position_native, captured_at_ms=observation.captured_at_ms, uncertainty=visual.uncertainty_native)
                self._last_evidence_at_ms[role_id] = int(observation.captured_at_ms)
                self._last_accepted_visual_sequence[role_id] = int(observation.sequence)
                accepted_positions[role_id] = tuple(float(value) for value in role.state.position_native)
                continue
            # Keep the previous *accepted* visual anchor.  A candidate that is
            # rejected by the innovation gate must not move the anchor or teach
            # the speed model; otherwise one false colour blob can enlarge the
            # gate and make subsequent drift self-reinforcing.
            previous_visual = role.last_visual_position
            previous_visual_at = role.last_visual_at_ms
            visual_gap_ms = (
                max(0, int(observation.captured_at_ms) - int(previous_visual_at))
                if previous_visual_at is not None
                else 0
            )
            calibrated_speed = (
                role.speed_calibrator.speed
                if role.speed_calibrator is not None
                else max(1.0, float(getattr(self.route_controller, "magnitude", 0.65)) * 100.0)
            )
            # Let a fresh, well-associated frame correct the command model over
            # the distance the model could have travelled since the previous
            # visual anchor.  The fixed 20px floor remains the unit-test and
            # false-candidate guard; the motion budget prevents a slow real
            # game from being rejected simply because the initial speed model
            # was optimistic.
            motion_budget = calibrated_speed * visual_gap_ms / 1000.0
            # A delayed observation is expressed at captured_at, while state
            # may already include accepted output after that instant. Rewind
            # only those receipt segments before fusing, then the normal tick
            # will replay them once to ``now``. This prevents double integration.
            observation_time = int(observation.captured_at_ms)
            rewind_x = rewind_y = 0.0
            for receipt in role.execution_receipts:
                start = int(receipt.accepted_at_ms)
                end = start + int(receipt.valid_for_ms)
                overlap = max(0, end - max(start, observation_time))
                if overlap <= 0:
                    continue
                rewind_x += float(receipt.vector[0]) * calibrated_speed * overlap / 1000.0
                rewind_y += float(receipt.vector[1]) * calibrated_speed * overlap / 1000.0
            fusion_position = (
                float(state.position_native[0]) - rewind_x,
                float(state.position_native[1]) - rewind_y,
            )
            fused = fuse_observation(
                fusion_position,
                visual.position_native,
                prediction_sigma=max(1.0, state.uncertainty_native),
                observation_sigma=max(1.0, visual.uncertainty_native),
                max_innovation=max(20.0, state.uncertainty_native * 3.0 + 10.0, motion_budget * 1.5 + 20.0),
                observation_confidence=visual.confidence,
            )
            self._evidence.record("fusion", role_id, "accepted" if fused.accepted else "innovation_rejected",
                sequence=observation.sequence, captured_at_ms=observation.captured_at_ms,
                predicted=fusion_position, candidate=visual.position_native, result=fused.position,
                innovation=math.dist(fusion_position, visual.position_native),
                limit=max(20.0, state.uncertainty_native * 3.0 + 10.0, motion_budget * 1.5 + 20.0),
                confidence=visual.confidence, speed=calibrated_speed)
            if fused.accepted:
                if previous_visual is not None:
                    latest_receipt = role.execution_receipts[-1] if role.execution_receipts else None
                    self._evidence.record("observed_motion", role_id, "visual_observation",
                        sequence=observation.sequence, before=previous_visual, after=visual.position_native,
                        displacement=math.dist(previous_visual, visual.position_native), interval_ms=visual_gap_ms,
                        receipt_sequence=None if latest_receipt is None else latest_receipt.sequence,
                        control_tick=None if latest_receipt is None else latest_receipt.control_tick,
                        evidence="visual_displacement_not_causal_proof")
                if (
                    role.speed_calibrator is not None
                    and previous_visual is not None
                    and previous_visual_at is not None
                    and visual_gap_ms > 0
                    and math.dist(previous_visual, visual.position_native) >= 0.5
                    and float(visual.confidence) >= 0.4
                ):
                    try:
                        role.speed_calibrator.update(
                            previous_visual,
                            visual.position_native,
                            visual_gap_ms,
                            confidence=float(visual.confidence),
                        )
                    except (TypeError, ValueError):
                        pass
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
                self._roles[role_id].execution_cursor_ms = max(
                    self._roles[role_id].execution_cursor_ms,
                    int(observation.captured_at_ms),
                )
                self._roles[role_id].misses = 0
                role.last_visual_position = tuple(float(value) for value in visual.position_native)
                role.last_visual_at_ms = int(observation.captured_at_ms)
                self._last_evidence_at_ms[role_id] = int(observation.captured_at_ms)
                self._last_accepted_visual_sequence[role_id] = int(observation.sequence)
                accepted_positions[role_id] = tuple(float(value) for value in role.state.position_native)
        source = self._live_target_source
        if source is not None and source in accepted_positions:
            self._refresh_live_target(source, accepted_positions[source])
        return True

    def _refresh_live_target(self, source: str, position: tuple[float, float]) -> None:
        """Propagate accepted leader evidence from any localization source."""
        if source != self._live_target_source:
            return
        for role_id in self._live_target_roles:
            if role_id != source:
                self.update_target(role_id, position)

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
            self._evidence.record("position_correction", role_id, source,
                before=None if role.state is None else role.state.position_native,
                after=values, sequence=None if self._latest_visual is None else self._latest_visual.sequence)
            last_visual = role.state.last_visual_at_ms if role.state is not None else None
            role.state = RoleTrackingState(role_id, values, (0.0, 0.0), uncertainty, last_visual, int(now_ms), source)
            role.odometry = CommandOdometry(values, uncertainty=uncertainty, captured_at_ms=int(now_ms))
            role.execution_cursor_ms = max(role.execution_cursor_ms, int(now_ms))
            role.last_visual_position = values
            role.last_visual_at_ms = int(now_ms)
            role.misses = 0
            self._last_evidence_at_ms[role_id] = int(now_ms)
            self._refresh_live_target(role_id, values)
            applied = True
        return applied

    def _poll_recovery_backends(self, *, now_ms: int) -> float:
        started = time.perf_counter()
        self._memory_succeeded_tick = self._memory_failed_tick = False
        self._memory_succeeded_roles.clear()
        self._global_succeeded_tick = self._global_failed_tick = False
        self._global_succeeded_roles.clear()
        self._memory_elapsed_tick = self._global_elapsed_tick = 0.0
        if self.memory_recovery is not None:
            result = self.memory_recovery.poll(self.token)
            if result is not None:
                self._memory_elapsed_tick = float(result.elapsed_ms)
                self._evidence.record("memory", "all", "failed" if result.error else "completed",
                    error=result.error, positions=result.positions, elapsed_ms=result.elapsed_ms)
                self._memory_recovery_timing.add(self._memory_elapsed_tick)
                if result.error:
                    self._memory_failed_tick = True
                else:
                    self._memory_succeeded_tick = self._apply_recovery_positions(
                        result.positions, now_ms=now_ms, source="memory_reanchor"
                    )
                    if self._memory_succeeded_tick:
                        self._memory_succeeded_roles.update(
                            str(role) for role, point in result.positions.items()
                            if str(role) in self._roles and point is not None
                        )
        if self.global_recovery is not None:
            result = self.global_recovery.poll(self.token, now_ms=now_ms)
            if result is not None:
                self._global_elapsed_tick = float(result.elapsed_ms)
                self._global_recovery_timing.add(self._global_elapsed_tick)
                if result.error:
                    self._global_failed_tick = True
                else:
                    value = result.value
                    positions = getattr(value, "positions", value)
                    if isinstance(positions, Mapping):
                        self._global_succeeded_tick = self._apply_recovery_positions(
                            positions, now_ms=now_ms, source="global_reanchor"
                        )
                        if self._global_succeeded_tick:
                            self._global_succeeded_roles.update(
                                str(role) for role, point in positions.items()
                                if str(role) in self._roles and point is not None
                            )
                    if not self._global_succeeded_tick:
                        # An empty or role-incomplete result is a completed
                        # recovery failure.  Feed it back to the backend so a
                        # bad global probe cannot be resubmitted every tick.
                        self._global_failed_tick = True
                        record_failure = getattr(self.global_recovery, "record_failure", None)
                        if callable(record_failure):
                            record_failure(now_ms=now_ms)
        return (time.perf_counter() - started) * 1000.0

    def _run_local_recovery(self, role_id: str, *, now_ms: int) -> tuple[bool, float]:
        association = {} if self._latest_visual is None else self._latest_visual.association_diagnostics
        if role_id in association.get("pending_roles", ()) or (
            association.get("single_candidate_pending") and association.get("single_candidate_role") == role_id
        ):
            self._evidence.record("local", role_id, "awaiting_second_frame")
            return False, 0.0
        if self.local_recovery is None or self.local_search is None or self._latest_frame is None:
            self._evidence.record("local", role_id, "missing_backend_or_exact_frame")
            return False, 0.0
        role = self._roles[role_id]
        if role.state is None:
            return False, 0.0
        started = time.perf_counter()
        search = (
            self.local_search.get(role_id)
            if isinstance(self.local_search, Mapping)
            else self.local_search
        )
        if search is None:
            return False, 0.0
        result = self.local_recovery.match(self._latest_frame, role.state.position_native, search)
        elapsed = (time.perf_counter() - started) * 1000.0
        self._local_recovery_timing.add(elapsed)
        if not result.valid or result.position_native is None:
            self._evidence.record("local", role_id, "no_match", sequence=self._latest_visual.sequence if self._latest_visual else None,
                elapsed_ms=elapsed)
            return False, elapsed
        # A local ROI result must agree with a visible candidate from the same
        # frame when one exists.  Without this cross-check, a nearby role or a
        # static minimap marker can be promoted as this role and overwrite the
        # live-follow target.  Keep prediction/miss evidence on disagreement;
        # the next frame or the low-frequency memory fallback can recover.
        visual_item = self._latest_visual.roles.get(role_id) if self._latest_visual is not None else None
        if visual_item is not None and visual_item.visible and visual_item.position_native is not None:
            consistency_limit = max(
                24.0,
                (role.state.uncertainty_native * 4.0 + 16.0) if role.state is not None else 24.0,
            )
            if math.dist(result.position_native, visual_item.position_native) > consistency_limit:
                self._evidence.record("local", role_id, "frame_candidate_conflict",
                    sequence=self._latest_visual.sequence, local=result.position_native,
                    frame=visual_item.position_native, limit=consistency_limit, elapsed_ms=elapsed)
                _LOGGER.info(
                    "step=follow_engine.local_recovery_rejected role=%s reason=frame_candidate_conflict "
                    "local=%s frame=%s distance=%.2f limit=%.2f",
                    role_id, result.position_native, visual_item.position_native,
                    math.dist(result.position_native, visual_item.position_native), consistency_limit,
                )
                return False, elapsed
        return self._apply_recovery_positions({role_id: result.position_native}, now_ms=now_ms, source="local_roi"), elapsed

    def _submit_memory_recovery(self, *, now_ms: int) -> bool:
        if self.memory_recovery is None or self.memory_recovery.in_flight or not self.memory_recovery.cooldown_ready(now_ms=now_ms):
            self._evidence.record("memory", "all", "unavailable" if self.memory_recovery is None else
                "in_flight" if self.memory_recovery.in_flight else "cooldown")
            return False
        submitted = self.memory_recovery.submit(self.token, now_ms=now_ms)
        self._evidence.record("memory", "all", "submitted" if submitted else "submit_declined")
        return submitted

    def _memory_cooldown_ready(self, *, now_ms: int) -> bool:
        return bool(self.memory_recovery and not self.memory_recovery.in_flight and self.memory_recovery.cooldown_ready(now_ms=now_ms))

    def _submit_global_recovery(self, *, now_ms: int) -> bool:
        if self.global_recovery is None or self.global_recovery.in_flight:
            self._evidence.record("global", "all", "unavailable" if self.global_recovery is None else "in_flight")
            return False
        cooldown_ready = getattr(self.global_recovery, "cooldown_ready", None)
        if callable(cooldown_ready) and not cooldown_ready(now_ms=now_ms):
            return False
        return self.global_recovery.submit(self.token, now_ms=now_ms)

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
        # A local ROI search and an A* replan are bounded control-plane work.
        # Never run both roles' expensive recovery in one tick; otherwise a
        # two-player miss serializes two image decodes and pushes the next
        # target/output tick behind the visual cadence.  Route controllers that
        # support ``allow_replan`` receive one full replan budget per tick and
        # use their cached corridor for the other role.
        latest_visual = self._latest_visual
        local_candidates = []
        if latest_visual is not None:
            for role_id, control in self._roles.items():
                visual_item = latest_visual.roles.get(role_id)
                evidence_at = self._last_evidence_at_ms.get(role_id, control.state.last_visual_at_ms if control.state else None)
                age = float("inf") if evidence_at is None else max(0.0, now - evidence_at)
                visible = bool(
                    visual_item
                    and visual_item.visible
                    and visual_item.position_native is not None
                    and age <= 600.0
                    and self._last_accepted_visual_sequence.get(role_id) == latest_visual.sequence
                )
                if control.state is not None and not visible and self._last_local_sequence.get(role_id) != latest_visual.sequence:
                    local_candidates.append(role_id)
        local_role = (
            local_candidates[self._local_recovery_turn % len(local_candidates)]
            if local_candidates else None
        )
        if local_candidates:
            self._local_recovery_turn = (self._local_recovery_turn + 1) % len(local_candidates)
        route_replan_used = False
        for role_id, control in self._roles.items():
            if control.state is None:
                continue
            if control.odometry is not None and control.execution_receipts:
                prediction_started = time.perf_counter()
                # Integrate only the not-yet-consumed overlap of accepted
                # leases.  Planned vectors are never movement evidence.
                cursor = int(control.execution_cursor_ms)
                for receipt in control.execution_receipts:
                    start = max(cursor, int(receipt.accepted_at_ms))
                    end = min(now, int(receipt.accepted_at_ms) + int(receipt.valid_for_ms))
                    if end <= start:
                        continue
                    cursor = end
                    if receipt.vector == (0.0, 0.0):
                        continue
                    speed = (
                        control.speed_calibrator.speed
                        if control.speed_calibrator is not None
                        else max(1.0, float(getattr(self.route_controller, "magnitude", 0.65)) * 100.0)
                    )
                    estimate = control.odometry.step(
                        receipt.vector,
                        speed,
                        end - start,
                        now_ms=end,
                        speed_error_units_per_second=20.0,
                        timing_error_ms=10.0,
                    )
                    control.state = RoleTrackingState(
                        role_id,
                        estimate.position,
                        estimate.velocity,
                        estimate.uncertainty,
                        control.state.last_visual_at_ms,
                        end,
                        "command_execution",
                    )
                control.execution_cursor_ms = max(cursor, control.execution_cursor_ms)
                # Drop only leases which are fully behind the cursor; retain
                # future-dated receipts for a later control tick.
                control.execution_receipts = [
                    item for item in control.execution_receipts
                    if int(item.accepted_at_ms) + int(item.valid_for_ms) > control.execution_cursor_ms
                ]
                prediction_ms += (time.perf_counter() - prediction_started) * 1000.0
            visual_item: RoleVisualObservation | None = visual.roles.get(role_id) if visual is not None else None
            evidence_at = self._last_evidence_at_ms.get(role_id, control.state.last_visual_at_ms)
            age = float("inf") if evidence_at is None else max(0.0, now - evidence_at)
            visible = bool(
                visual_item
                and visual_item.visible
                and visual_item.position_native is not None
                and age <= 600.0
                and self._last_accepted_visual_sequence.get(role_id) == visual.sequence
            )
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
                    memory_succeeded=role_id in self._memory_succeeded_roles,
                    memory_failed=self._memory_failed_tick,
                    global_in_flight=bool(self.global_recovery and self.global_recovery.in_flight),
                    global_succeeded=role_id in self._global_succeeded_roles,
                    global_failed=self._global_failed_tick,
                    host_session_expired=self._host_session_expired,
                    map_instance_valid=self._map_instance_valid,
                    transform_valid=self._transform_valid,
                    consecutive_misses=control.misses,
                    prediction_uncertainty=control.state.uncertainty_native,
                )
            )
            if decision.action.value == "local_retry" and visual is not None and role_id == local_role:
                self._last_local_sequence[role_id] = visual.sequence
                local_succeeded, elapsed_ms = self._run_local_recovery(role_id, now_ms=now)
                local_ms += elapsed_ms
                if local_succeeded:
                    control.state = self._roles[role_id].state
                    age = 0.0
                    self._last_accepted_visual_sequence[role_id] = int(visual.sequence)
                decision = self.recovery_policy.decide(
                    RecoveryObservation(
                        frame_available=True,
                        frame_age_ms=age if math.isfinite(age) else None,
                        visual_match=visible or local_succeeded,
                        local_attempted=True,
                        local_succeeded=local_succeeded,
                        memory_in_flight=bool(self.memory_recovery and self.memory_recovery.in_flight),
                        memory_cooldown_ready=self._memory_cooldown_ready(now_ms=now),
                        memory_succeeded=role_id in self._memory_succeeded_roles,
                        memory_failed=self._memory_failed_tick,
                        global_in_flight=bool(self.global_recovery and self.global_recovery.in_flight),
                        global_succeeded=role_id in self._global_succeeded_roles,
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
                global_requested = self._submit_global_recovery(now_ms=now)
            decisions.append(decision)
            self._evidence.record("recovery", role_id, decision.reason,
                action=decision.action.value, level=int(decision.level),
                misses=control.misses, uncertainty=control.state.uncertainty_native,
                age_ms=age if math.isfinite(age) else None,
                local_attempted=local_attempted, memory_configured=self.memory_recovery is not None,
                memory_in_flight=bool(self.memory_recovery and self.memory_recovery.in_flight),
                memory_cooldown_ready=self._memory_cooldown_ready(now_ms=now),
                global_configured=self.global_recovery is not None)
            route: RouteDecision | None = None
            if control.target is not None:
                route_started = time.perf_counter()
                route_controller = self._route_controllers[role_id]
                allow_replan = not route_replan_used
                before_replans = getattr(route_controller, "replan_count", None)
                if getattr(route_controller, "supports_bounded_replan", False):
                    route = route_controller.plan(
                        control.state.position_native,
                        control.target,
                        allow_replan=allow_replan,
                    )
                else:
                    try:
                        route = route_controller.plan(
                            control.state.position_native,
                            control.target,
                            now_ms=now,
                            position_source=control.state.source,
                        )
                    except TypeError:
                        # Keep injected test/compatibility controllers on the
                        # original two-argument contract.
                        route = route_controller.plan(control.state.position_native, control.target)
                after_replans = getattr(route_controller, "replan_count", None)
                if before_replans is not None and after_replans is not None and after_replans > before_replans:
                    route_replan_used = True
                route_ms += (time.perf_counter() - route_started) * 1000.0
                route_points.extend(route.route)
                # Dynamic follow must not stop merely because command
                # odometry crossed the arrival radius.  Until a fresh visual
                # (or recovery) observation is accepted, keep the last valid
                # pulse alive so the next frame can correct the prediction.
                if (
                    route.arrived
                    and control.state.source in {"command_prediction", "command_execution"}
                ):
                    route = RouteDecision(
                        route_controller.corrective_vector(
                            control.state.position_native,
                            control.target,
                            fallback=control.last_vector,
                        ),
                        max(1, int(getattr(self.route_controller, "duration_ms", 80))),
                        route.distance,
                        False,
                        route.route,
                        "predicted_arrival_unconfirmed",
                    )
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
            if control.controller is not None:
                intents.append(OutputIntent(role_id, control.controller, vector, duration, neutral=vector == (0.0, 0.0),
                    control_tick=self._tick_sequence, target_revision=control.target_revision,
                    visual_sequence=-1 if visual is None else visual.sequence))
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
        role_diag: dict[str, object] = {}
        for role_id, control in self._roles.items():
            state = control.state
            visual_item = None if self._latest_visual is None else self._latest_visual.roles.get(role_id)
            latest_sequence = None if self._latest_visual is None else int(self._latest_visual.sequence)
            accepted_sequence = self._last_accepted_visual_sequence.get(role_id)
            evidence_at = self._last_evidence_at_ms.get(role_id)
            role_diag[role_id] = {
                "target": control.target,
                "target_revision": control.target_revision,
                "position": None if state is None else state.position_native,
                "source": None if state is None else state.source,
                "uncertainty": None if state is None else float(state.uncertainty_native),
                "visual_visible": None if visual_item is None else bool(visual_item.visible),
                "visual_position": None if visual_item is None else visual_item.position_native,
                "latest_visual_sequence": latest_sequence,
                "accepted_visual_sequence": accepted_sequence,
                "visual_accepted": latest_sequence is not None and accepted_sequence == latest_sequence,
                "visual_age_ms": None if evidence_at is None else max(0, now - int(evidence_at)),
                "misses": int(control.misses),
                "last_vector": tuple(float(v) for v in control.last_vector),
                "last_duration_ms": int(control.last_duration_ms),
            }
        self._last_control_diagnostics = {
            "tick_sequence": int(self._tick_sequence),
            "latest_visual_sequence": None if self._latest_visual is None else int(self._latest_visual.sequence),
            "latest_visual_captured_at_ms": None if self._latest_visual is None else int(self._latest_visual.captured_at_ms),
            "live_target_source": self._live_target_source,
            "live_target_roles": tuple(self._live_target_roles),
            "recovery_state": snapshot.recovery_state,
            "recovery_reason": snapshot.recovery_reason,
            "decisions": tuple({
                "state": decision.state.value,
                "level": int(decision.level),
                "action": decision.action.value,
                "reason": decision.reason,
                "keep_session": bool(decision.keep_session),
            } for decision in decisions),
            "roles": role_diag,
            "intents": tuple({
                "role": intent.role_id,
                "controller": int(intent.controller),
                "vector": tuple(float(v) for v in intent.vector),
                "duration_ms": int(intent.duration_ms),
                "neutral": bool(intent.neutral),
                "control_tick": intent.control_tick,
                "target_revision": intent.target_revision,
                "visual_sequence": intent.visual_sequence,
            } for intent in snapshot.output_intents),
            "timing": {
                "total_ms": float(total_ms),
                "recovery_ms": float(recovery_poll_ms + local_ms),
                "route_ms": float(route_ms),
            },
        }
        self._tick_timing.add(total_ms)
        self._recovery_chain_timing.add(recovery_poll_ms + local_ms)
        self._last_snapshot = snapshot
        return snapshot

    def stop(self) -> None:
        self._session_active = False
        for backend in (self.memory_recovery, self.global_recovery):
            close = getattr(backend, "close", None)
            if callable(close):
                close()

    def close(self) -> None:
        """Release asynchronous recovery resources at process shutdown."""

        self.stop()
        if self._frame_ring is not None:
            try:
                self._frame_ring.close()
            except Exception:
                pass
            self._frame_ring = None

    def snapshot(self) -> FusionSnapshot | None:
        return self._last_snapshot

    def diagnostics(self) -> dict[str, object]:
        """Return offline-safe control timing and queue-age evidence."""
        return {
            "tick_duration_ms": self._tick_timing.as_dict("tick_"),
            "recovery_chain_duration_ms": self._recovery_chain_timing.as_dict("recovery_chain_"),
            "local_recovery_duration_ms": self._local_recovery_timing.as_dict("local_recovery_"),
            "memory_recovery_duration_ms": self._memory_recovery_timing.as_dict("memory_recovery_"),
            "global_recovery_duration_ms": self._global_recovery_timing.as_dict("global_recovery_"),
            "queue_depth": self._queue_depth,
            "queue_age_ms": self._queue_age_ms,
            "last_tick_sequence": self._tick_sequence,
            "last_control_decision": dict(self._last_control_diagnostics),
            "diagnostic_events": self._evidence.snapshot(),
        }


@dataclass(frozen=True, slots=True)
class ControlProcessEvent:
    kind: str
    snapshot: FusionSnapshot | None = None
    error: str = ""
    traceback_text: str = ""
    tick_sequence: int = 0
    diagnostics: dict[str, object] = field(default_factory=dict)


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
    frame_ring: SharedFrameRing | None = None,
    observation_role_ids: tuple[str, ...] | None = None,
    priority_command_queue=None,
    target_command_queue=None,
) -> None:
    runtime: FollowControlRuntime | None = None
    terminal_error = False
    last_channel_sequence = {"visual": 0, "priority": 0, "target": 0, "command": 0}
    try:
        token = GenerationToken(int(generation), str(map_instance))
        # The default remains the pure offline runtime.  A caller that has a
        # spawn-safe composition (for example one with a warm memory backend
        # and a bounded local search) can inject it without making this
        # process know about Qt, PoE2 or Host adapters.
        runtime = (
            runtime_factory(token, roles)
            if runtime_factory is not None
            else FollowControlRuntime(
                token,
                roles,
                frame_ring=frame_ring,
                observation_role_ids=observation_role_ids,
            )
        )
        if not isinstance(runtime, FollowControlRuntime):
            raise TypeError("runtime_factory must return FollowControlRuntime")
        if frame_ring is not None and runtime_factory is not None:
            runtime.attach_frame_ring(frame_ring)
        while not stop_event.is_set():
            tick_started = time.perf_counter()
            should_stop = False
            # The queues have independent transport order.  A single global
            # sequence gate is incorrect: a newer target can arrive before an
            # older receipt from another feeder thread.  Coalesce replaceable
            # visual/target state first, then consume priority commands in
            # their own FIFO order.  Each queue has a bounded drain budget so
            # a producer burst cannot starve the control tick indefinitely.
            target_latest: dict[str, Mapping[str, Any]] = {}
            visual_items: list[Mapping[str, Any]] = []
            priority_batch: list[Mapping[str, Any]] = []
            for queue_name, channel in (
                ("target", target_command_queue),
                ("priority", priority_command_queue),
                ("visual", command_queue),
            ):
                if channel is None:
                    continue
                for _ in range(64):
                    try:
                        item = channel.get_nowait()
                    except queue.Empty:
                        break
                    if not isinstance(item, Mapping):
                        _put_latest(output_queue, ControlProcessEvent("command_error", error="command must be a mapping"))
                        continue
                    if item.get("kind") == "target" and queue_name == "target":
                        role_id = item.get("role_id")
                        if role_id is not None:
                            previous = target_latest.get(str(role_id))
                            if previous is None or int(item.get("sequence", 0)) > int(previous.get("sequence", 0)):
                                target_latest[str(role_id)] = item
                    elif item.get("kind") == "visual" and queue_name == "visual":
                        visual_items.append(item)
                    elif queue_name == "priority":
                        priority_batch.append(item)

            def _valid(command: Mapping[str, Any], channel_name: str) -> bool:
                try:
                    command_generation = int(command["generation"])
                    command_sequence = int(command["sequence"])
                except (KeyError, TypeError, ValueError):
                    _put_latest(output_queue, ControlProcessEvent("command_error", error="command header is invalid"))
                    return False
                if command_generation != int(generation) or command_sequence <= last_channel_sequence[channel_name]:
                    return False
                last_channel_sequence[channel_name] = command_sequence
                return True

            priority_batch.sort(key=lambda item: int(item.get("sequence", 0)))
            for command in priority_batch:
                if not _valid(command, "priority"):
                    continue
                if not isinstance(command, Mapping):
                    _put_latest(output_queue, ControlProcessEvent("command_error", error="command must be a mapping"))
                    continue
                kind = str(command.get("kind", ""))
                if kind == "recovery_signal":
                    signal = command.get("signal")
                    if signal is None:
                        _put_latest(output_queue, ControlProcessEvent("command_error", error="recovery command has no signal"))
                        continue
                    runtime.signal_recovery(signal)
                elif kind == "execution":
                    receipt = command.get("receipt")
                    if not runtime.record_execution(receipt):
                        _put_latest(output_queue, ControlProcessEvent("command_error", error="execution receipt rejected"))
                elif kind == "execution_gap":
                    runtime.signal_execution_gap(
                        str(command.get("role_id", "")),
                        sequence=int(command.get("sequence", 0)),
                    )
                elif kind == "stop":
                    runtime.stop()
                    should_stop = True
                    break
                else:
                    _put_latest(output_queue, ControlProcessEvent("command_error", error=f"unknown command kind: {kind}"))
            if should_stop or stop_event.is_set():
                break

            # Preserve the first visual anchor and the newest correction in a
            # burst. Intermediate frames are replaceable and can be dropped.
            visual_batch = visual_items[:1]
            if len(visual_items) > 1:
                visual_batch.append(visual_items[-1])
            for visual_command in visual_batch:
                if not _valid(visual_command, "visual"):
                    continue
                observation = visual_command.get("observation")
                if observation is None:
                    _put_latest(output_queue, ControlProcessEvent("command_error", error="visual command has no observation"))
                else:
                    runtime.apply_visual(observation, frame=visual_command.get("frame"))
            for role_id, command in sorted(target_latest.items()):
                if _valid(command, "target"):
                    runtime.update_target(role_id, command.get("target"))
            snapshot = runtime.tick(now_ms=int(time.time() * 1000))
            tick_sequence = int(getattr(runtime, "_tick_sequence", 0))
            runtime_diagnostics = runtime.diagnostics()
            _put_latest(
                output_queue,
                ControlProcessEvent(
                    "snapshot",
                    snapshot=snapshot,
                    tick_sequence=tick_sequence,
                    diagnostics=runtime_diagnostics,
                ),
            )
            if tick_sequence == 1 or tick_sequence % 30 == 0:
                intent_diag = [
                    {
                        "role": intent.role_id,
                        "controller": intent.controller,
                        "vector": tuple(round(float(value), 4) for value in intent.vector),
                        "duration_ms": int(intent.duration_ms),
                        "neutral": bool(intent.neutral),
                    }
                    for intent in snapshot.output_intents
                ]
                _LOGGER.info(
                    "step=follow_engine.control_child_progress generation=%s tick=%s "
                    "drained_visual=%s drained_target=%s drained_priority=%s tick_ms=%.1f pid=%s",
                    generation, tick_sequence, len(visual_items), len(target_latest),
                    len(priority_batch), (time.perf_counter() - tick_started) * 1000.0,
                    mp.current_process().pid,
                )
                _LOGGER.info(
                    "step=follow_engine.control_decision generation=%s tick=%s "
                    "roles=%s recovery=%s reason=%s intents=%s",
                    generation, tick_sequence, snapshot.roles, snapshot.recovery_state,
                    snapshot.recovery_reason, intent_diag,
                )
            # The interval is a start-to-start period. Processing time is
            # already part of this period; adding another full sleep here was
            # the main source of avoidable follower lag under recovery/A* load.
            stop_event.wait(
                _cadence_wait_seconds(started=tick_started, interval_ms=interval_ms)
            )
    except BaseException as exc:  # pragma: no cover - exercised in spawned process
        terminal_error = True
        _put_latest(
            output_queue,
            ControlProcessEvent("error", error=f"{type(exc).__name__}: {exc}", traceback_text=traceback.format_exc()),
        )
    finally:
        if runtime is not None:
            try:
                runtime.close()
            except Exception:
                pass
        # Keep the structured error observable.  A latest-only queue must not
        # overwrite an error with the normal stopped marker in the same turn.
        if not terminal_error:
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
        frame_ring: SharedFrameRing | None = None,
        observation_role_ids: tuple[str, ...] | None = None,
    ) -> None:
        if int(interval_ms) < 1:
            raise ValueError("interval_ms must be positive")
        self.roles = dict(roles)
        self.interval_ms = int(interval_ms)
        self.runtime_factory = runtime_factory
        self.frame_ring = frame_ring
        self.observation_role_ids = tuple(str(role) for role in (observation_role_ids or self.roles))
        self.context = context or mp.get_context("spawn")
        self.stop_event = self.context.Event()
        self.commands = self.context.Queue(maxsize=16)
        # Visual frames are latest-only and may be dropped under load. Target,
        # execution and lifecycle commands are control-plane messages and must
        # not be evicted by that visual stream.
        self.priority_commands = self.context.Queue(maxsize=8)
        # Targets are latest-only state, not a FIFO control event.  Keeping
        # them separate from execution receipts prevents a burst of output
        # feedback from delaying the follower's newest leader position.
        # Keep enough slots for one latest value per controlled role.  The
        # parent coalesces by role before enqueueing; a single slot would let
        # p1 updates evict p2 updates during a burst.
        self.target_commands = self.context.Queue(maxsize=max(1, len(self.roles)))
        self.events = self.context.Queue(maxsize=1)
        self.process = None
        self._command_generation: int | None = None
        self._channel_sequences = {"visual": 0, "priority": 0, "target": 0, "command": 0}
        # Target updates are replaceable control-plane state.  Keep the newest
        # one outside the bounded priority queue when a burst of execution
        # receipts temporarily fills that queue, then flush it as soon as the
        # parent observes the queue has room again.
        self._pending_targets: dict[str, tuple[float, float] | None] = {}
        # Execution receipts are evidence for odometry and therefore cannot
        # use latest-only semantics.  Keep a bounded FIFO spill buffer when
        # the small priority queue is temporarily full; unlike visual frames,
        # a receipt is never silently discarded.
        self._pending_executions = deque(maxlen=256)
        self._execution_overflow_count = 0
        self._priority_overflow = False
        self._pending_execution_gaps: deque[dict] = deque(maxlen=64)

    @staticmethod
    def _drain(queue_object) -> None:
        while True:
            try:
                queue_object.get_nowait()
            except queue.Empty:
                return

    def start(self, *, generation: int, map_instance: str) -> None:
        if self.process is not None and self.process.is_alive():
            raise RuntimeError("control process is already running")
        self._drain(self.commands)
        self._pending_targets.clear()
        self._pending_executions.clear()
        self._priority_overflow = False
        self._pending_execution_gaps.clear()
        self._drain_priority_preserving_targets()
        self._drain(self.target_commands)
        self._drain(self.events)
        self.stop_event.clear()
        self._command_generation = int(generation)
        for channel in self._channel_sequences:
            self._channel_sequences[channel] = 0
        if self.frame_ring is not None:
            # FollowEnginePort starts control before vision.  Bind the ring
            # before spawning control so a map change is reflected in the
            # child's immutable ring spec, not only in the parent object.
            self.frame_ring.rebind_session(map_instance=str(map_instance))
        self.process = self.context.Process(
            target=control_process_entry,
            args=(
                self.roles, int(generation), str(map_instance), self.commands,
                self.events, self.stop_event, self.interval_ms, self.runtime_factory,
                self.frame_ring, self.observation_role_ids, self.priority_commands,
                self.target_commands,
            ),
            name=f"poe2-follow-control-{generation}",
            daemon=True,
        )
        self.process.start()
        _LOGGER.info(
            "step=follow_engine.control_process_started handle_id=%s pid=%s alive=%s generation=%s roles=%s",
            id(self), getattr(self.process, "pid", None), self.process.is_alive(), generation,
            tuple(self.roles),
        )
        self._flush_pending_targets()

    def send_visual(self, observation: VisualObservation, *, frame: object | None = None) -> None:
        self._send({"kind": "visual", "observation": observation, "frame": frame})

    def update_target(self, role_id: str, target: tuple[float, float] | None) -> None:
        self._send({"kind": "target", "role_id": str(role_id), "target": target})

    def send_recovery_signal(self, signal: str) -> None:
        self._send({"kind": "recovery_signal", "signal": str(signal)})

    def send_execution(self, receipt: ExecutionReceipt) -> None:
        self._send({"kind": "execution", "receipt": receipt})

    def poll_latest(self) -> ControlProcessEvent | None:
        self._flush_pending_executions()
        self._flush_pending_targets()
        latest = None
        while True:
            try:
                latest = self.events.get_nowait()
            except queue.Empty:
                return latest

    def stop(self, *, timeout: float = 2.0) -> None:
        process_pid = getattr(self.process, "pid", None) if self.process is not None else None
        _LOGGER.info(
            "step=follow_engine.control_process_stop_requested handle_id=%s pid=%s alive=%s timeout_s=%.2f",
            id(self), process_pid,
            self.process.is_alive() if self.process is not None else False, timeout,
        )
        try:
            self._send({"kind": "stop"})
        except Exception:
            pass
        self.stop_event.set()
        process = self.process
        if process is None:
            return
        forced = stop_process(process, timeout=timeout)
        if forced and self.frame_ring is not None:
            self.frame_ring.invalidate()
        self.process = None
        self._command_generation = None
        self._pending_targets.clear()
        self._pending_executions.clear()
        _LOGGER.info(
            "step=follow_engine.control_process_stopped handle_id=%s pid=%s forced=%s alive=False",
            id(self), process_pid, forced,
        )

    def dispose(self) -> None:
        self.stop()
        close_queues(self.commands, self.priority_commands, self.target_commands, self.events)
        _LOGGER.info(
            "step=follow_engine.control_queues_closed handle_id=%s commands=%s priority=%s target=%s events=%s",
            id(self), id(self.commands), id(self.priority_commands), id(self.target_commands), id(self.events),
        )

    def _send(self, command: dict) -> None:
        if self._command_generation is None:
            return
        self._flush_pending_executions()
        self._flush_pending_targets()
        envelope = dict(command)
        envelope["generation"] = self._command_generation
        kind = envelope.get("kind")
        if kind == "target":
            channel_name = "target"
            # Before a child process is started there is no target consumer;
            # keep the pre-start command on the control plane so it is visible
            # to lifecycle probes and can be flushed when start() binds the
            # target channel. Once started, targets always use their isolated
            # latest-only channel.
            channel = self.priority_commands if self.process is None else self.target_commands
        elif kind in {"execution", "recovery_signal", "stop"}:
            channel_name = "priority"
            channel = self.priority_commands
        else:
            channel_name = "visual"
            channel = self.commands
        self._channel_sequences[channel_name] += 1
        envelope["channel"] = channel_name
        envelope["sequence"] = self._channel_sequences[channel_name]
        # Once a priority command is pending, all later execution/recovery
        # commands must join that FIFO.  Otherwise a consumer freeing one slot
        # between flush() and put_nowait() can allow a newer command to bypass
        # an older receipt (e.g. delivery [2, 1]), which the child sequence
        # gate correctly rejects.
        if envelope.get("kind") in {"execution", "recovery_signal"} and self._pending_executions:
            self._defer_priority_envelope(envelope)
            return
        for _ in range(4):
            try:
                channel.put_nowait(envelope)
                return
            except queue.Full:
                # Visual data is replaceable; control-plane commands are not.
                # If the priority channel is full, replace only an older
                # command of the same class as a last resort (target updates
                # are latest-only, while stop remains on the stop_event path).
                if channel is self.commands:
                    try:
                        channel.get_nowait()
                    except queue.Empty:
                        continue
                elif envelope.get("kind") == "target":
                    # Target values are replaceable state. Drain only target
                    # envelopes, merge them by role, and put the newest set
                    # back. Priority commands are never displaced.
                    self._pending_targets[str(envelope.get("role_id"))] = envelope.get("target")
                    self._drain_target_channel_into_pending()
                    self._flush_pending_targets()
                    return
                elif envelope.get("kind") == "execution":
                    self._defer_priority_envelope(envelope)
                    return
                elif envelope.get("kind") == "recovery_signal":
                    self._defer_priority_envelope(envelope)
                    return
                else:
                    return
        # A saturated queue is a recoverable transport condition.  Do not
        # propagate queue.Full into the Qt/UI thread.

    def _flush_pending_targets(self) -> None:
        """Try to enqueue the newest target for each role without blocking."""
        if self._command_generation is None or not self._pending_targets:
            return
        for role_id, target in tuple(self._pending_targets.items()):
            self._channel_sequences["target"] += 1
            envelope = {
                "kind": "target",
                "role_id": role_id,
                "target": target,
                "generation": self._command_generation,
                "channel": "target",
                "sequence": self._channel_sequences["target"],
            }
            target_channel = self.target_commands if self.process is not None else self.priority_commands
            try:
                target_channel.put_nowait(envelope)
            except queue.Full:
                # Preserve the value and stop trying until the next parent
                # send/poll.  No command is evicted from the priority channel.
                self._channel_sequences["target"] -= 1
                return
            self._pending_targets.pop(role_id, None)

    def _defer_priority_envelope(self, envelope: dict) -> None:
        """Retain priority commands in order and expose overflow explicitly."""
        if len(self._pending_executions) >= self._pending_executions.maxlen:
            self._execution_overflow_count += 1
            self._priority_overflow = True
            receipt = envelope.get("receipt")
            if receipt is not None and len(self._pending_execution_gaps) < self._pending_execution_gaps.maxlen:
                self._pending_execution_gaps.append({
                    "kind": "execution_gap",
                    "role_id": str(getattr(receipt, "role_id", "")),
                    "sequence": int(getattr(receipt, "sequence", 0)),
                    "generation": self._command_generation,
                    "channel": "priority",
                })
            _LOGGER.error(
                "step=follow_engine.priority_command_overflow generation=%s kind=%s "
                "count=%s pending=%s",
                self._command_generation, envelope.get("kind"),
                self._execution_overflow_count, len(self._pending_executions),
            )
            return
        self._pending_executions.append(envelope)
        if envelope.get("kind") == "execution":
            _LOGGER.debug(
                "step=follow_engine.execution_receipt_deferred generation=%s pending=%s",
                self._command_generation, len(self._pending_executions),
            )

    def _flush_pending_executions(self) -> None:
        """Flush all priority spill entries without reordering or eviction."""
        if self._command_generation is None:
            return
        while self._pending_execution_gaps:
            envelope = self._pending_execution_gaps[0]
            try:
                self.priority_commands.put_nowait(envelope)
            except queue.Full:
                return
            self._pending_execution_gaps.popleft()
        while self._pending_executions:
            envelope = self._pending_executions[0]
            try:
                self.priority_commands.put_nowait(envelope)
            except queue.Full:
                return
            self._pending_executions.popleft()

    def _drain_target_channel_into_pending(self) -> None:
        """Merge queued target state without touching priority commands."""
        while True:
            try:
                item = self.target_commands.get_nowait()
            except queue.Empty:
                return
            if not isinstance(item, Mapping) or item.get("kind") != "target":
                continue
            role_id = item.get("role_id")
            if role_id is not None:
                self._pending_targets[str(role_id)] = item.get("target")

    def _drain_priority_preserving_targets(self) -> None:
        """Drop stale priority work at start but carry pre-start targets over."""
        while True:
            try:
                item = self.priority_commands.get_nowait()
            except queue.Empty:
                return
            if isinstance(item, Mapping) and item.get("kind") == "target":
                role_id = item.get("role_id")
                if role_id is not None:
                    self._pending_targets[str(role_id)] = item.get("target")


__all__ = ["ControlProcessEvent", "FollowControlProcessHandle", "FollowControlRuntime", "control_process_entry"]
