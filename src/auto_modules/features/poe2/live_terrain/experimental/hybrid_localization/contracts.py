"""Replaceable boundaries for hybrid localization capabilities."""

from __future__ import annotations

from typing import Any, Mapping, Protocol, runtime_checkable

from auto_modules.features.poe2.live_terrain.terrain_reference import TerrainReference

from .models import AbsoluteRegistration, HybridFrame, PositionAnchor


@runtime_checkable
class AnchorProvider(Protocol):
    def read_once(self, expected_instance_id: str) -> PositionAnchor: ...


@runtime_checkable
class AbsoluteRegistrar(Protocol):
    last_diagnostics: Mapping[str, Any]

    def register(
        self,
        frame: HybridFrame,
        *,
        reference: TerrainReference,
        anchor: PositionAnchor,
        prior: AbsoluteRegistration | None = None,
    ) -> AbsoluteRegistration | None: ...


@runtime_checkable
class LocalTracker(Protocol):
    def track(
        self,
        frame: HybridFrame,
        *,
        reference: TerrainReference,
        previous_frame: HybridFrame,
        previous: AbsoluteRegistration,
    ) -> AbsoluteRegistration | None: ...


__all__ = ["AbsoluteRegistrar", "AnchorProvider", "LocalTracker"]
