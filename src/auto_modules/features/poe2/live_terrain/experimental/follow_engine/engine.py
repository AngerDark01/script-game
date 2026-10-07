"""UI-independent composition port for the dual-channel follow engine."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Protocol

from .contracts import FusionSnapshot
from .generation import GenerationClock, GenerationToken


class VisionPort(Protocol):
    def start(self, *, generation: int, map_instance: str) -> None: ...

    def poll_latest(self) -> Any: ...

    def stop(self, *, timeout: float = 2.0) -> None: ...


class ControlPort(Protocol):
    def start(self, *, generation: int, map_instance: str) -> None: ...

    def send_visual(self, observation: Any) -> None: ...

    def update_target(self, role_id: str, target: tuple[float, float] | None) -> None: ...

    def poll_latest(self) -> Any: ...

    def stop(self, *, timeout: float = 2.0) -> None: ...


class OutputPort(Protocol):
    def start(self) -> None: ...

    def apply(self, snapshot: FusionSnapshot) -> None: ...

    def stop(self, *, force: bool = True) -> None: ...


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
    ) -> None:
        self.vision = vision
        self.control = control
        self.output = output
        self.clock = generation_clock or GenerationClock()
        self.token: GenerationToken | None = None
        self._active = False
        self._last_snapshot: FusionSnapshot | None = None
        self._last_error: str = ""

    @property
    def active(self) -> bool:
        return self._active

    def start(self, config: FollowEngineStart) -> GenerationToken:
        if self._active:
            raise RuntimeError("follow engine is already active")
        token = self.clock.begin(config.map_instance)
        started_vision = False
        started_control = False
        try:
            self.control.start(generation=token.generation, map_instance=token.map_instance)
            started_control = True
            self.vision.start(generation=token.generation, map_instance=token.map_instance)
            started_vision = True
            self.output.start()
        except Exception:
            if started_vision:
                self.vision.stop()
            if started_control:
                self.control.stop()
            self.output.stop(force=True)
            self.clock.stop()
            raise
        self.token = token
        self._active = True
        self._last_snapshot = None
        self._last_error = ""
        return token

    def update_target(self, target: tuple[float, float] | None, *, role_id: str | None = None) -> None:
        if not self._active:
            raise RuntimeError("follow engine is not active")
        if role_id is None:
            raise ValueError("role_id is required when updating a composed engine")
        normalized = None if target is None else (float(target[0]), float(target[1]))
        self.control.update_target(str(role_id), normalized)

    def poll(self) -> FusionSnapshot | None:
        """Drain latest vision/control events without waiting on either process."""
        if not self._active:
            return self._last_snapshot
        vision_event = self.vision.poll_latest()
        if vision_event is not None and getattr(vision_event, "kind", "") == "observation":
            observation = getattr(vision_event, "observation", None)
            if observation is not None:
                self.control.send_visual(observation)
        elif vision_event is not None and getattr(vision_event, "kind", "") == "error":
            self._last_error = str(getattr(vision_event, "error", "vision_error"))

        control_event = self.control.poll_latest()
        if control_event is None:
            return self._last_snapshot
        kind = str(getattr(control_event, "kind", ""))
        if kind == "snapshot":
            snapshot = getattr(control_event, "snapshot", None)
            if snapshot is not None:
                self._last_snapshot = snapshot
                self.output.apply(snapshot)
                return snapshot
        elif kind == "error":
            self._last_error = str(getattr(control_event, "error", "control_error"))
        return self._last_snapshot

    def snapshot(self) -> FusionSnapshot | None:
        return self._last_snapshot

    def diagnostics(self) -> dict[str, object]:
        return {
            "active": self._active,
            "generation": self.token.generation if self.token is not None else None,
            "map_instance": self.token.map_instance if self.token is not None else None,
            "last_error": self._last_error,
        }

    def stop(self, *, reason: str = "user") -> None:
        if not self._active:
            return
        try:
            self.vision.stop()
        finally:
            try:
                self.control.stop()
            finally:
                self.output.stop(force=True)
                self._active = False
                self.clock.stop()
                self.token = None
                self._last_error = "" if reason == "user" else str(reason)


__all__ = ["ControlPort", "FollowEnginePort", "FollowEngineStart", "OutputPort", "VisionPort"]
