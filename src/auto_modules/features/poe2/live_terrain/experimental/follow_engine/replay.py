"""Deterministic, side-effect-free replay manifests for follow-engine tests."""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from .contracts import ObservationSource, RoleVisualObservation, VisualObservation
from .control.follow_control_process import FollowControlRuntime
from .generation import GenerationClock


def _finite_point(value: Any, field: str) -> tuple[float, float]:
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        raise ValueError(f"{field} must contain two numeric values")
    point = (float(value[0]), float(value[1]))
    if not all(math.isfinite(item) for item in point):
        raise ValueError(f"{field} must contain finite values")
    return point


@dataclass(frozen=True, slots=True)
class ReplayEvent:
    captured_at_ms: int
    kind: str
    roles: Mapping[str, tuple[float, float] | None]
    expected_state: str
    keep_session: bool

    def __post_init__(self) -> None:
        timestamp = int(self.captured_at_ms)
        kind = str(self.kind).strip()
        expected_state = str(self.expected_state).strip()
        if timestamp < 0 or not kind or not expected_state:
            raise ValueError("replay event metadata is invalid")
        normalized: dict[str, tuple[float, float] | None] = {}
        for role, position in dict(self.roles).items():
            role_key = str(role).strip()
            if not role_key:
                raise ValueError("replay role must be non-empty")
            normalized[role_key] = None if position is None else _finite_point(position, f"roles[{role_key}]")
        object.__setattr__(self, "captured_at_ms", timestamp)
        object.__setattr__(self, "kind", kind)
        object.__setattr__(self, "expected_state", expected_state)
        object.__setattr__(self, "roles", normalized)
        object.__setattr__(self, "keep_session", bool(self.keep_session))


@dataclass(frozen=True, slots=True)
class ReplayManifest:
    name: str
    map_instance: str
    roles: tuple[str, ...]
    events: tuple[ReplayEvent, ...]
    real_input_allowed: bool = False

    def __post_init__(self) -> None:
        name = str(self.name).strip()
        map_instance = str(self.map_instance).strip()
        roles = tuple(str(role).strip() for role in self.roles)
        if not name or not map_instance or not roles or any(not role for role in roles):
            raise ValueError("replay manifest identity is invalid")
        if len(set(roles)) != len(roles):
            raise ValueError("replay roles must be unique")
        events = tuple(self.events)
        if not events:
            raise ValueError("replay manifest must contain events")
        timestamps = [event.captured_at_ms for event in events]
        if timestamps != sorted(timestamps):
            raise ValueError("replay events must be ordered by timestamp")
        for event in events:
            unknown = set(event.roles) - set(roles)
            if unknown:
                raise ValueError(f"replay event contains unknown roles: {sorted(unknown)}")
        object.__setattr__(self, "name", name)
        object.__setattr__(self, "map_instance", map_instance)
        object.__setattr__(self, "roles", roles)
        object.__setattr__(self, "events", events)
        object.__setattr__(self, "real_input_allowed", bool(self.real_input_allowed))

    def signature(self) -> str:
        """Return a stable digest used to prove deterministic offline replay."""
        payload = {
            "name": self.name,
            "map_instance": self.map_instance,
            "roles": self.roles,
            "events": [
                {
                    "captured_at_ms": event.captured_at_ms,
                    "kind": event.kind,
                    "roles": dict(sorted(event.roles.items())),
                    "expected_state": event.expected_state,
                    "keep_session": event.keep_session,
                }
                for event in self.events
            ],
        }
        encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()


def load_replay_manifest(path: str | Path) -> ReplayManifest:
    """Load one offline manifest without touching any runtime integration."""
    source = Path(path)
    payload = json.loads(source.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or payload.get("schema_version") != 1:
        raise ValueError("unsupported replay manifest schema")
    events = []
    for item in payload.get("events", []):
        if not isinstance(item, dict):
            raise ValueError("replay event must be an object")
        expected = item.get("expected", {})
        if not isinstance(expected, dict):
            raise ValueError("replay event expected must be an object")
        events.append(
            ReplayEvent(
                captured_at_ms=item.get("captured_at_ms", 0),
                kind=item.get("kind", ""),
                roles=item.get("roles", {}),
                expected_state=expected.get("state", ""),
                keep_session=expected.get("keep_session", True),
            )
        )
    return ReplayManifest(
        name=payload.get("name", ""),
        map_instance=payload.get("map_instance", ""),
        roles=tuple(payload.get("roles", ())),
        events=tuple(events),
        real_input_allowed=payload.get("real_input_allowed", False),
    )


def load_replay_scenarios(path: str | Path) -> tuple[ReplayManifest, ...]:
    """Load the scenario collection used by the offline follow gate."""
    source = Path(path)
    payload = json.loads(source.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or payload.get("schema_version") != 1:
        raise ValueError("unsupported replay manifest schema")
    common = {
        "map_instance": payload.get("map_instance", ""),
        "roles": tuple(payload.get("roles", ())),
        "real_input_allowed": payload.get("real_input_allowed", False),
    }
    scenarios = payload.get("scenarios", ())
    if not isinstance(scenarios, list) or not scenarios:
        raise ValueError("replay scenarios must be a non-empty list")
    manifests = []
    for scenario in scenarios:
        if not isinstance(scenario, dict):
            raise ValueError("replay scenario must be an object")
        events = []
        for item in scenario.get("events", ()):
            expected = item.get("expected", {})
            if not isinstance(expected, dict):
                raise ValueError("replay event expected must be an object")
            events.append(
                ReplayEvent(
                    captured_at_ms=item.get("captured_at_ms", 0),
                    kind=item.get("kind", ""),
                    roles=item.get("roles", {}),
                    expected_state=expected.get("state", ""),
                    keep_session=expected.get("keep_session", True),
                )
            )
        manifests.append(ReplayManifest(name=scenario.get("name", ""), events=tuple(events), **common))
    return tuple(manifests)


@dataclass(frozen=True, slots=True)
class ReplayRunResult:
    name: str
    signature: str
    states: tuple[str, ...]
    session_kept: bool
    expected_keep_session: bool


class OfflineReplayRunner:
    """Run replay events through the process-safe control runtime only."""

    def run(self, manifest: ReplayManifest) -> ReplayRunResult:
        if manifest.real_input_allowed:
            raise ValueError("offline replay cannot allow real input")
        token = GenerationClock().begin(manifest.map_instance)
        runtime = FollowControlRuntime(token, {role: index + 1 for index, role in enumerate(manifest.roles)})
        states: list[str] = []
        expected_keep = True
        for sequence, event in enumerate(manifest.events, start=1):
            roles = {
                role: RoleVisualObservation(
                    role,
                    point,
                    confidence=1.0 if point is not None else 0.0,
                    uncertainty_native=1.0 if point is not None else 0.0,
                    visible=point is not None,
                    last_visual_at_ms=event.captured_at_ms if point is not None else None,
                )
                for role, point in event.roles.items()
            }
            runtime.apply_visual(
                VisualObservation(
                    generation=token.generation,
                    sequence=sequence,
                    captured_at_ms=event.captured_at_ms,
                    map_instance=token.map_instance,
                    roles=roles,
                    source=ObservationSource.VISUAL if event.kind == "visual" else ObservationSource.PARTIAL,
                )
            )
            if event.kind in {"host_session_expired", "map_changed"}:
                runtime.signal_recovery(event.kind)
            snapshot = runtime.tick(now_ms=event.captured_at_ms)
            states.append(snapshot.recovery_state)
            expected_keep = expected_keep and event.keep_session
            if not snapshot.session_active:
                raise AssertionError(f"replay released session: {manifest.name}/{event.kind}")
        return ReplayRunResult(manifest.name, manifest.signature(), tuple(states), runtime.session_active, expected_keep)


__all__ = [
    "OfflineReplayRunner",
    "ReplayEvent",
    "ReplayManifest",
    "ReplayRunResult",
    "load_replay_manifest",
    "load_replay_scenarios",
]
