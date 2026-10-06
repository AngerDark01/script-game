"""Target sources shared by click, role and replay follow experiments."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


class TargetSource(Protocol):
    def latest(self) -> tuple[float, float] | None: ...


@dataclass
class MutableTargetSource:
    _target: tuple[float, float] | None = None

    def set(self, target: tuple[float, float] | None) -> None:
        self._target = None if target is None else (float(target[0]), float(target[1]))

    def latest(self) -> tuple[float, float] | None:
        return self._target


@dataclass
class RoleTargetSource:
    role_key: str
    _target: tuple[float, float] | None = None

    def update(self, target: tuple[float, float] | None) -> None:
        self._target = target

    def latest(self) -> tuple[float, float] | None:
        return self._target
