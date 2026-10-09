"""Explicit, spawn-safe assembly for the modular follow engine.

This module owns composition only.  It accepts capture and output adapters from
the caller, builds the vision processor from a first-frame seed bundle, and
connects one shared frame ring to the vision and control workers.  It does not
choose a real screenshot backend, memory reader, Host client, or gamepad.
"""

from __future__ import annotations

import math
from contextlib import ExitStack
from dataclasses import dataclass, field, replace
import logging
import threading
from typing import Any, Callable, Mapping, Sequence

from auto_modules.features.poe2.live_terrain.experimental.hybrid_localization.models import SimilarityTransform2D
from auto_modules.features.poe2.live_terrain.experimental.multiplayer_localization.models import MarkerColorProfile

from .control.follow_control_process import FollowControlProcessHandle, FollowControlRuntime
from .control.route_controller import RouteController
from .engine import FollowEnginePort, FollowEngineStart, OutputPort, RebuildBundle
from .recovery.local_recovery import LocalRecoveryBackend
from .recovery.memory_recovery import MemoryRecoveryBackend
from .shared_frame_ring import SharedFrameRing
from .vision.capture_adapter import FrameCapture
from .vision.dual_observation_processor import DualObservationProcessor, default_wall_extractor
from .vision.local_roi_search import EncodedMarkerRoiSearch
from .vision.vision_process import VisionProcessHandle


_LOGGER = logging.getLogger("auto_modules.poe2_live_terrain.follow_engine")
from .vision.dual_observation_processor import WallExtractor


@dataclass(frozen=True, slots=True)
class FollowSeedBundle:
    """Validated first-frame facts needed by both workers."""

    map_instance: str
    roles: Mapping[str, int]
    initial_positions_native: Mapping[str, tuple[float, float]]
    observation_role_ids: Sequence[str] | None = None
    initial_screen_positions: Mapping[str, tuple[float, float]] | None = None
    transform: SimilarityTransform2D | None = None
    marker_profiles: Sequence[MarkerColorProfile] = ()
    identity_hints: Mapping[str, str] | None = None
    max_candidates: int | None = None

    def __post_init__(self) -> None:
        instance = str(self.map_instance).strip()
        roles = {str(role).strip(): int(controller) for role, controller in self.roles.items()}
        observed = tuple(
            str(role).strip()
            for role in (self.observation_role_ids if self.observation_role_ids is not None else roles)
        )
        positions = {}
        for role, raw_point in self.initial_positions_native.items():
            if not isinstance(raw_point, (tuple, list)) or len(raw_point) != 2:
                raise ValueError("initial native positions must contain two values")
            point = (float(raw_point[0]), float(raw_point[1]))
            positions[str(role).strip()] = point
        if not instance or not roles or any(not role or controller < 1 for role, controller in roles.items()):
            raise ValueError("seed map instance and roles are required")
        if not observed or len(set(observed)) != len(observed) or any(not role for role in observed):
            raise ValueError("observation_role_ids must contain unique non-empty roles")
        if not set(roles).issubset(observed):
            raise ValueError("controlled roles must be included in observation_role_ids")
        if set(positions) != set(observed):
            raise ValueError("initial native positions must match roles/observation roles")
        if any(not all(math.isfinite(value) for value in point) for point in positions.values()):
            raise ValueError("initial native positions must be finite")
        screens = None
        if self.initial_screen_positions is not None:
            screens = {}
            for role, raw_point in self.initial_screen_positions.items():
                if not isinstance(raw_point, (tuple, list)) or len(raw_point) != 2:
                    raise ValueError("initial screen positions must contain two values")
                point = (float(raw_point[0]), float(raw_point[1]))
                if not all(math.isfinite(value) for value in point):
                    raise ValueError("initial screen positions must be finite")
                screens[str(role).strip()] = point
            if set(screens) != set(observed):
                raise ValueError("initial screen positions must match observation roles")
        if self.max_candidates is not None and int(self.max_candidates) < len(roles):
            raise ValueError("max_candidates must cover every role")
        object.__setattr__(self, "map_instance", instance)
        object.__setattr__(self, "roles", roles)
        object.__setattr__(self, "observation_role_ids", observed)
        object.__setattr__(self, "initial_positions_native", positions)
        object.__setattr__(self, "initial_screen_positions", screens)
        object.__setattr__(self, "marker_profiles", tuple(self.marker_profiles))
        object.__setattr__(self, "identity_hints", {str(key): str(value) for key, value in (self.identity_hints or {}).items()})
        if self.max_candidates is not None:
            object.__setattr__(self, "max_candidates", int(self.max_candidates))


@dataclass(frozen=True, slots=True)
class SpawnSafeFollowRuntimeFactory:
    """Pickle-safe factory for per-process recovery and route adapters.

    The source, transform and route controller are deliberately optional.  A
    real PoE2 reader is supplied by a higher-level adapter only when the caller
    explicitly opts into warm memory recovery; the default composition keeps
    the existing visual/prediction path unchanged.
    """

    local_search: Callable[[object, tuple[float, float], float], Any] | None = None
    route_controller: RouteController | None = None
    memory_source: Any | None = None
    memory_source_factory: Callable[[], Any] | None = None
    memory_transform: Callable[[tuple[float, float]], tuple[float, float]] | None = None
    memory_cooldown_ms: int = 8_000
    expected_players: int = 2
    observation_role_ids: tuple[str, ...] = ()
    live_target_source: str | None = None
    live_target_roles: tuple[str, ...] = ()
    live_target_initial_position: tuple[float, float] | None = None

    def __post_init__(self) -> None:
        if self.memory_source is not None and self.memory_source_factory is not None:
            raise ValueError("memory_source and memory_source_factory are mutually exclusive")
        source_configured = self.memory_source is not None or self.memory_source_factory is not None
        if source_configured != (self.memory_transform is not None):
            raise ValueError("a memory source/source_factory and memory_transform must be provided together")
        if int(self.memory_cooldown_ms) < 0 or int(self.expected_players) < 1:
            raise ValueError("memory recovery configuration is invalid")
        object.__setattr__(self, "observation_role_ids", tuple(str(role) for role in self.observation_role_ids))

    def __call__(self, token, roles):
        memory_recovery = None
        source = self.memory_source_factory() if self.memory_source_factory is not None else self.memory_source
        if source is not None:
            memory_recovery = MemoryRecoveryBackend(
                source,
                transform=self.memory_transform,
                cooldown_ms=int(self.memory_cooldown_ms),
                expected_players=int(self.expected_players),
            )
        return FollowControlRuntime(
            token,
            roles,
            route_controller=self.route_controller,
            local_recovery=LocalRecoveryBackend() if self.local_search is not None else None,
            local_search=self.local_search,
            memory_recovery=memory_recovery,
            observation_role_ids=self.observation_role_ids or tuple(roles),
            live_target_source=self.live_target_source,
            live_target_roles=self.live_target_roles,
            live_target_initial_position=self.live_target_initial_position,
        )


@dataclass(slots=True)
class FollowEngineComposition:
    """Owned resources for one opt-in engine session."""

    seed: FollowSeedBundle
    ring: SharedFrameRing
    vision: VisionProcessHandle
    control: FollowControlProcessHandle
    port: FollowEnginePort
    _rebuild_lock: threading.RLock = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self._rebuild_lock = threading.RLock()

    def start(self):
        return self.port.start(FollowEngineStart(self.seed.map_instance, self.seed.roles))

    def stop(self, *, reason: str = "user") -> None:
        _LOGGER.info(
            "step=follow_engine.composition_stop_begin composition_id=%s ring_id=%s reason=%s vision_id=%s control_id=%s",
            id(self), id(self.ring), id(self.port.vision), id(self.port.control), reason,
        )
        try:
            self.port.stop(reason=reason)
        finally:
            try:
                # The port may have replaced a stalled worker generation;
                # dispose the current handles rather than stale constructor
                # references.
                with self._rebuild_lock:
                    current_vision = self.port.vision
                    current_control = self.port.control
                current_vision.dispose()
            finally:
                try:
                    current_control.dispose()
                finally:
                    _LOGGER.info("step=follow_engine.ring_close_begin composition_id=%s ring_id=%s", id(self), id(self.ring))
                    self.ring.close(unlink=True)
                    _LOGGER.info("step=follow_engine.ring_closed composition_id=%s ring_id=%s", id(self), id(self.ring))
        _LOGGER.info(
            "step=follow_engine.composition_stop_finished composition_id=%s ring_id=%s reason=%s",
            id(self), id(self.ring), reason,
        )


def build_follow_engine_composition(
    *,
    seed: FollowSeedBundle,
    capture: FrameCapture,
    output: OutputPort,
    interval_ms: int = 33,
    ring_capacity: int = 3,
    ring_slot_size: int = 4 * 1024 * 1024,
    route_controller: RouteController | None = None,
    memory_source: Any | None = None,
    memory_source_factory: Callable[[], Any] | None = None,
    memory_transform: Callable[[tuple[float, float]], tuple[float, float]] | None = None,
    memory_cooldown_ms: int = 8_000,
    wall_extractor: WallExtractor | None = None,
    live_target_source: str | None = None,
    live_target_roles: Sequence[str] = (),
    live_target_initial_position: tuple[float, float] | None = None,
) -> FollowEngineComposition:
    """Build a complete offline-capable composition without side effects.

    ``route_controller`` and the memory pair are explicit opt-ins.  They are
    constructed inside the control process, so recovery readers do not run in
    the UI or vision process and a slow read cannot block frame processing.
    """
    controller_instance = getattr(route_controller, "map_instance", None)
    if controller_instance is not None and str(controller_instance) != seed.map_instance:
        raise ValueError("route controller map instance does not match follow seed")
    if int(interval_ms) < 1:
        raise ValueError("interval_ms must be positive")
    local_search = (
        {
            str(role): EncodedMarkerRoiSearch(
                marker_profiles=seed.marker_profiles,
                transform=seed.transform,
                identity_hint=(seed.identity_hints or {}).get(str(role)),
            )
            for role in seed.observation_role_ids
        }
        if seed.identity_hints
        else EncodedMarkerRoiSearch(marker_profiles=seed.marker_profiles, transform=seed.transform)
    )
    runtime_factory = SpawnSafeFollowRuntimeFactory(
            local_search=local_search,
            route_controller=route_controller,
            memory_source=memory_source,
            memory_source_factory=memory_source_factory,
            memory_transform=memory_transform,
            memory_cooldown_ms=memory_cooldown_ms,
            expected_players=len(seed.observation_role_ids),
            observation_role_ids=seed.observation_role_ids,
            live_target_source=None if live_target_source is None else str(live_target_source),
            live_target_roles=tuple(str(role) for role in live_target_roles),
            live_target_initial_position=live_target_initial_position,
    )
    with ExitStack() as cleanup:
        ring = SharedFrameRing(capacity=ring_capacity, slot_size=ring_slot_size, map_instance=seed.map_instance)
        cleanup.callback(ring.close, unlink=True)
        def make_workers(
            worker_ring,
            initial_positions_override=None,
            *,
            transform_override: SimilarityTransform2D | None = None,
            handover_transform: bool = False,
        ):
            initial_positions = dict(seed.initial_positions_native)
            if initial_positions_override:
                for role, point in initial_positions_override.items():
                    if str(role) in initial_positions:
                        initial_positions[str(role)] = (float(point[0]), float(point[1]))
            active_transform = seed.transform if not handover_transform else transform_override
            # A replacement processor must derive screen anchors from the
            # handed-over native positions and transform.  Reusing the
            # original screen anchors would mix two registration generations
            # after the minimap has scrolled.
            initial_screen_positions = (
                seed.initial_screen_positions if not handover_transform else None
            )
            processor = DualObservationProcessor(
                generation=1, map_instance=seed.map_instance, role_ids=tuple(seed.observation_role_ids),
                marker_profiles=seed.marker_profiles, initial_positions_native=initial_positions,
                initial_screen_positions=initial_screen_positions, transform=active_transform,
                identity_hints=seed.identity_hints, max_candidates=seed.max_candidates,
                wall_extractor=wall_extractor or default_wall_extractor,
            )
            # The control process receives its own pickle of the local search.
            # Build it from the same transform as Vision so a local recovery
            # cannot continue using the stale first-frame registration.
            worker_local_search = (
                {
                    str(role): EncodedMarkerRoiSearch(
                        marker_profiles=seed.marker_profiles,
                        transform=active_transform,
                        identity_hint=(seed.identity_hints or {}).get(str(role)),
                    )
                    for role in seed.observation_role_ids
                }
                if seed.identity_hints
                else EncodedMarkerRoiSearch(
                    marker_profiles=seed.marker_profiles,
                    transform=active_transform,
                )
            )
            worker_runtime_factory = replace(runtime_factory, local_search=worker_local_search)
            vision_handle = VisionProcessHandle(capture, processor, interval_ms=interval_ms, frame_ring=worker_ring)
            control_handle = FollowControlProcessHandle(
                seed.roles, interval_ms=interval_ms, runtime_factory=worker_runtime_factory,
                frame_ring=worker_ring, observation_role_ids=tuple(seed.observation_role_ids),
            )
            return vision_handle, control_handle

        vision, control = make_workers(ring)
        cleanup.callback(vision.dispose)
        cleanup.callback(control.dispose)
        owner_ref = {}

        def rebuild_workers():
            owner = owner_ref["owner"]
            # Carry the last fused native positions into the replacement
            # processor. A worker stall must not silently restart association
            # around the original first-frame anchor after the party has
            # already crossed the map.
            handoff_positions = {}
            previous = owner.port.snapshot()
            if previous is not None:
                handoff_positions = {
                    str(role): tuple(state.position_native)
                    for role, state in previous.roles.items()
                    if state.position_native is not None
                }
            latest_observation = getattr(owner.port, "latest_visual_observation", None)
            handoff_has_observation = latest_observation is not None
            # Legacy/fake processors may emit observations without the new
            # opaque transform field.  Preserve the accepted seed transform
            # in that case instead of handing ``None`` to the replacement.
            handoff_transform = seed.transform
            if handoff_has_observation:
                handoff_transform = getattr(latest_observation, "transform", None) or seed.transform
            if not handoff_positions and handoff_has_observation:
                roles = getattr(latest_observation, "roles", {})
                handoff_positions = {
                    str(role): tuple(observation.position_native)
                    for role, observation in roles.items()
                    if getattr(observation, "position_native", None) is not None
                }
            replacement_ring = SharedFrameRing(
                capacity=ring_capacity, slot_size=ring_slot_size, map_instance=seed.map_instance,
            )
            try:
                replacement_vision, replacement_control = make_workers(
                    replacement_ring,
                    handoff_positions,
                    transform_override=handoff_transform,
                    handover_transform=handoff_has_observation,
                )
            except Exception:
                replacement_ring.close(unlink=True)
                raise
            old_ring = owner.ring
            old_vision = owner.vision
            old_control = owner.control

            def commit() -> None:
                with owner._rebuild_lock:
                    owner.ring = replacement_ring
                    owner.vision = replacement_vision
                    owner.control = replacement_control

            def retire() -> None:
                for component in (old_vision, old_control):
                    dispose = getattr(component, "dispose", None)
                    if callable(dispose):
                        try:
                            dispose()
                        except Exception:
                            # The port already stopped these handles before
                            # commit; a queue-close failure must not roll back
                            # the atomically selected replacement generation.
                            pass
                try:
                    old_ring.close(unlink=True)
                except Exception:
                    pass

            def dispose() -> None:
                for component in (replacement_vision, replacement_control):
                    try:
                        component.dispose()
                    except Exception:
                        try:
                            component.stop(timeout=2.0)
                        except Exception:
                            pass
                replacement_ring.close(unlink=True)

            return RebuildBundle(
                replacement_vision,
                replacement_control,
                commit=commit,
                dispose=dispose,
                retire=retire,
            )

        port = FollowEnginePort(
            vision=vision, control=control, output=output,
            rebuild_factory=rebuild_workers,
            control_owns_live_targets=(live_target_source is not None and bool(live_target_roles)),
        )
        owner = FollowEngineComposition(seed, ring, vision, control, port)
        owner_ref["owner"] = owner
        cleanup.pop_all()
        return owner


__all__ = [
    "FollowEngineComposition",
    "FollowSeedBundle",
    "SpawnSafeFollowRuntimeFactory",
    "build_follow_engine_composition",
]
