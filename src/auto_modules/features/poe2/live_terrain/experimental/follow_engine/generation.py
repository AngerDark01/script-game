"""Session generation and sequence gates for asynchronous follow workers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class GenerationToken:
    generation: int
    map_instance: str

    def __post_init__(self) -> None:
        generation = int(self.generation)
        map_instance = str(self.map_instance).strip()
        if generation <= 0 or not map_instance:
            raise ValueError("generation token is invalid")
        object.__setattr__(self, "generation", generation)
        object.__setattr__(self, "map_instance", map_instance)


class GenerationClock:
    """Create monotonically increasing tokens and invalidate old workers."""

    def __init__(self) -> None:
        self._next_generation = 0
        self._active: GenerationToken | None = None

    @property
    def active(self) -> GenerationToken | None:
        return self._active

    def begin(self, map_instance: str) -> GenerationToken:
        self._next_generation += 1
        self._active = GenerationToken(self._next_generation, map_instance)
        return self._active

    def stop(self) -> None:
        self._active = None

    def is_current(self, generation: int, map_instance: str) -> bool:
        active = self._active
        return bool(
            active is not None
            and int(generation) == active.generation
            and str(map_instance).strip() == active.map_instance
        )


class SequenceGate:
    """Accept only new messages belonging to the active generation."""

    def __init__(self, token: GenerationToken) -> None:
        self.token = token
        self.last_sequence = -1
        self.stale_count = 0

    def accept(self, message: Any) -> bool:
        generation = getattr(message, "generation", None)
        sequence = getattr(message, "sequence", None)
        if sequence is None:
            sequence = getattr(message, "tick_sequence", None)
        map_instance = getattr(message, "map_instance", None)
        if not self.token_matches(generation, map_instance) or sequence is None:
            self.stale_count += 1
            return False
        sequence = int(sequence)
        if sequence <= self.last_sequence:
            self.stale_count += 1
            return False
        self.last_sequence = sequence
        return True

    def token_matches(self, generation: Any, map_instance: Any) -> bool:
        return int(generation) == self.token.generation and str(map_instance).strip() == self.token.map_instance


__all__ = ["GenerationClock", "GenerationToken", "SequenceGate"]
