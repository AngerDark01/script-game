from __future__ import annotations

from copy import deepcopy
from typing import Any, Callable, Mapping

from .algorithms.base import AlgorithmDescriptor


AlgorithmFactory = Callable[[Mapping[str, Any]], Any]


class AlgorithmRegistry:
    """Discoverable registry for detector factories and extension points."""

    def __init__(self) -> None:
        self._descriptors: dict[str, AlgorithmDescriptor] = {}
        self._factories: dict[str, AlgorithmFactory | None] = {}

    def register(self, descriptor: AlgorithmDescriptor, factory: AlgorithmFactory | None) -> None:
        if descriptor.algorithm_id in self._descriptors:
            raise ValueError(f"duplicate algorithm id: {descriptor.algorithm_id}")
        if descriptor.status != "unavailable" and factory is None:
            raise ValueError("available algorithms require a factory")
        self._descriptors[descriptor.algorithm_id] = descriptor
        self._factories[descriptor.algorithm_id] = factory

    def descriptor(self, algorithm_id: str) -> AlgorithmDescriptor:
        try:
            return self._descriptors[algorithm_id]
        except KeyError as exc:
            raise KeyError(f"unknown algorithm id: {algorithm_id}") from exc

    def descriptors(self) -> list[AlgorithmDescriptor]:
        return list(self._descriptors.values())

    def create(self, algorithm_id: str, parameters: Mapping[str, Any] | None = None) -> Any:
        descriptor = self.descriptor(algorithm_id)
        if descriptor.status == "unavailable":
            raise RuntimeError(f"algorithm is unavailable: {algorithm_id}")
        factory = self._factories[algorithm_id]
        if factory is None:
            raise RuntimeError(f"algorithm has no factory: {algorithm_id}")
        return factory(deepcopy(dict(parameters or {})))
