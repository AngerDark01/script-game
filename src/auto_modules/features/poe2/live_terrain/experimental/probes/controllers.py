"""Target-only probe controllers; movement is delegated to a shared runtime."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ProbeTarget:
    position: tuple[float, float]
    source: str


class MoveProbe:
    def __init__(self) -> None:
        self.armed = False
        self.target: ProbeTarget | None = None

    def arm(self) -> None:
        self.armed = True
        self.target = None

    def select(self, position: tuple[float, float]) -> ProbeTarget:
        if not self.armed:
            raise RuntimeError("move probe is not armed")
        self.target = ProbeTarget((float(position[0]), float(position[1])), "click")
        return self.target

    def stop(self) -> None:
        self.armed = False
        self.target = None


class DualTargetProbe(MoveProbe):
    def select(self, position: tuple[float, float]) -> ProbeTarget:
        target = super().select(position)
        return ProbeTarget(target.position, "shared_target")
