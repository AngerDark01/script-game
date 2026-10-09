"""Concrete PoE2 adapters for the modular follow-engine page path."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from auto_modules.features.poe2.live_terrain.experimental.follow_engine.composition import (
    FollowSeedBundle,
    build_follow_engine_composition,
)
from auto_modules.features.poe2.live_terrain.experimental.follow_engine.control.route_controller import (
    MapAwareRouteController,
    LegacyDynamicFollowRouteController,
)
from auto_modules.features.poe2.live_terrain.experimental.follow_engine.control.snapshot_output import (
    SnapshotOutputAdapter,
)
from auto_modules.features.poe2.live_terrain.experimental.follow_engine.control.async_output import (
    AsyncSnapshotOutput,
)
from auto_modules.features.poe2.live_terrain.experimental.follow_engine.engine import FollowEnginePort
from auto_modules.features.poe2.live_terrain.experimental.follow_engine.ui_adapter import FollowEngineUiAdapter
from auto_modules.features.poe2.live_terrain.experimental.follow_engine.vision.capture_adapter import EncodedImageCapture
from auto_modules.features.poe2.live_terrain.experimental.follow_engine.vision.poe2_monitor_capture import (
    Poe2WallMaskExtractor,
    SpawnSafePoe2MonitorCapture,
)
from auto_modules.features.poe2.live_terrain.experimental.multiplayer_localization.models import MarkerColorProfile
from auto_modules.features.poe2.live_terrain.experimental.multiplayer_localization.memory_anchors import (
    Poe2DualPlayerPositionSource,
)
from auto_modules.features.poe2.live_terrain.orientation import TerrainOrientation
from auto_modules.ui.modes.poe2_live_terrain.follow_engine_adapter import Poe2FollowEnginePageAdapter


@dataclass(frozen=True, slots=True)
class Poe2NativeMemoryTransform:
    """Pickle-safe world-grid to oriented native-map transform."""

    orientation: TerrainOrientation
    native_shape: tuple[int, int]

    def __call__(self, point: tuple[float, float]) -> tuple[float, float]:
        return self.orientation.transform_point(point, self.native_shape)


def build_follow_seed_from_dual_result(
    *,
    map_instance: str,
    result: Any,
    roles: Mapping[str, int],
    max_candidates: int | None = None,
    marker_profiles: Sequence[MarkerColorProfile] = (),
    initial_candidates: Sequence[Any] = (),
) -> FollowSeedBundle:
    """Convert the accepted dual first-frame result into one shared seed.

    The result's identity keys are authoritative.  No P1/P2 names are
    invented here, and controlled roles may be a strict subset of the observed
    identities for leader/follower modes.
    """
    if not bool(getattr(result, "accepted", False)):
        raise ValueError("dual first-frame result must be accepted")
    players = getattr(result, "players", {})
    if not isinstance(players, Mapping) or not players:
        raise ValueError("accepted dual result has no players")
    initial_native = {
        str(identity): tuple(float(value) for value in player.mapped_position)
        for identity, player in players.items()
    }
    initial_screen = {
        str(identity): tuple(float(value) for value in player.screen_position)
        for identity, player in players.items()
    }
    registration = getattr(result, "primary_registration", None)
    transform = getattr(registration, "transform", None)
    if transform is None:
        raise ValueError("accepted dual result has no similarity transform")
    controlled = {str(role): int(controller) for role, controller in roles.items()}
    if not set(controlled).issubset(initial_native):
        raise ValueError("controlled roles are absent from dual first-frame result")
    candidates_by_id = {
        str(getattr(candidate, "candidate_id", "")): candidate
        for candidate in initial_candidates
        if str(getattr(candidate, "candidate_id", ""))
    }
    identity_hints = {
        str(identity): str(
            getattr(candidates_by_id.get(str(player.candidate_id)), "color_features", {}).get("identity_hint") or ""
        )
        for identity, player in players.items()
        if str(player.candidate_id) in candidates_by_id
    }
    if not identity_hints or len(identity_hints) != len(players) or len(set(identity_hints.values())) != len(identity_hints) or not all(identity_hints.values()):
        identity_hints = {}
    return FollowSeedBundle(
        map_instance=str(map_instance),
        roles=controlled,
        observation_role_ids=tuple(initial_native),
        initial_positions_native=initial_native,
        initial_screen_positions=initial_screen,
        transform=transform,
        marker_profiles=tuple(marker_profiles),
        identity_hints=identity_hints,
        max_candidates=max_candidates or max(6, len(initial_native) * 3),
    )


def build_poe2_follow_engine_page_adapter(
    *,
    seed: FollowSeedBundle,
    monitor_config: Any,
    program_output_factory: Any,
    wall_map: Any,
    native_shape: tuple[int, int] | None = None,
    leader_role: str | None = None,
    target_roles: Sequence[str] = (),
    interval_ms: int | None = None,
    arm_delay_ms: int = 10_000,
    capture_backend_factory: Any | None = None,
) -> tuple[Poe2FollowEnginePageAdapter, Any]:
    """Build the real PoE2 capture/output composition behind a page adapter.

    Construction is side-effect free: the screenshot backend is lazy and Host
    outputs are created only when the first control snapshot has an intent.
    The returned composition must be retained by the page and stopped on the
    explicit user stop path so its shared ring can be unlinked.
    """
    if program_output_factory is None or not callable(program_output_factory):
        raise ValueError("program_output_factory is required for position testing")
    binding = getattr(monitor_config, "binding", None)
    if binding is None:
        raise ValueError("PoE2 monitor binding is required for modular follow")
    provider = SpawnSafePoe2MonitorCapture(
        binding,
        shape=getattr(monitor_config, "shape", "square"),
        radius=getattr(monitor_config, "circle_radius", None),
        **({"backend_factory": capture_backend_factory} if capture_backend_factory is not None else {}),
    )
    capture = EncodedImageCapture(
        provider,
        generation=1,
        map_instance=seed.map_instance,
        image_format=".png",
    )
    wall_extractor = Poe2WallMaskExtractor(
        getattr(monitor_config, "recognizer_params", {})
    )
    synchronous_output = SnapshotOutputAdapter(
        output_factory=lambda role_id, controller: program_output_factory(int(controller)),
        continuous_roles=set(seed.roles),
        arm_delay_ms=int(arm_delay_ms),
    )
    # Host writes are synchronous named-pipe calls.  Keep them behind a
    # latest-only actor so capture/control/UI polling never waits on a device
    # round trip; offline compositions may still inject the synchronous
    # adapter directly for deterministic contract tests.
    output = AsyncSnapshotOutput(synchronous_output)
    route_controller = LegacyDynamicFollowRouteController(wall_map)
    cadence_ms = int(interval_ms or max(
        16,
        round(1000 / max(1, int(getattr(monitor_config, "localization_fps", 30)))),
    ))
    memory_kwargs = {}
    if native_shape is not None:
        memory_kwargs = {
            "memory_source_factory": Poe2DualPlayerPositionSource,
            "memory_transform": Poe2NativeMemoryTransform(
                TerrainOrientation(), tuple(native_shape)
            ),
            "memory_cooldown_ms": 8_000,
        }
    composition = build_follow_engine_composition(
        seed=seed,
        capture=capture,
        output=output,
        interval_ms=cadence_ms,
        route_controller=route_controller,
        wall_extractor=wall_extractor,
        live_target_source=leader_role,
        live_target_roles=tuple(target_roles),
        live_target_initial_position=(
            seed.initial_positions_native.get(str(leader_role))
            if leader_role is not None else None
        ),
        **memory_kwargs,
    )
    adapter = Poe2FollowEnginePageAdapter(
        FollowEngineUiAdapter(composition.port),
        initial_positions=seed.initial_positions_native,
        leader_role=leader_role,
        target_roles=target_roles,
    )
    return adapter, composition


__all__ = [
    "build_follow_seed_from_dual_result",
    "build_poe2_follow_engine_page_adapter",
]
