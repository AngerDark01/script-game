from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any, Mapping


SUPPORTED_SELECTION_STRATEGIES = frozenset({"confidence", "first", "nearest"})


@dataclass(frozen=True)
class AlgorithmProfile:
    """One configured instance of a reusable perception algorithm."""

    instance_id: str
    algorithm_id: str
    parameters: dict[str, Any] = field(default_factory=dict)
    enabled: bool = True
    weight: float = 1.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.instance_id or not self.algorithm_id:
            raise ValueError("algorithm profile identifiers must not be empty")
        if float(self.weight) < 0.0:
            raise ValueError("algorithm profile weight must not be negative")
        object.__setattr__(self, "parameters", dict(self.parameters))
        object.__setattr__(self, "metadata", dict(self.metadata))

    def to_dict(self) -> dict[str, Any]:
        return {
            "instance_id": self.instance_id,
            "algorithm_id": self.algorithm_id,
            "parameters": deepcopy(self.parameters),
            "enabled": bool(self.enabled),
            "weight": float(self.weight),
            "metadata": deepcopy(self.metadata),
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "AlgorithmProfile":
        return cls(
            instance_id=str(payload.get("instance_id", "")),
            algorithm_id=str(payload.get("algorithm_id", "")),
            parameters=dict(payload.get("parameters") or {}),
            enabled=bool(payload.get("enabled", True)),
            weight=float(payload.get("weight", 1.0)),
            metadata=dict(payload.get("metadata") or {}),
        )


@dataclass(frozen=True)
class TargetProfile:
    """Game/scene/target configuration consumed by the perception runner."""

    game_id: str
    scene_id: str
    target_type: str
    algorithms: tuple[AlgorithmProfile, ...] = ()
    min_confidence: float = 0.5
    confirmation_frames: int = 1
    selection_strategy: str = "confidence"
    metadata: dict[str, Any] = field(default_factory=dict)
    schema_version: int = 1

    def __post_init__(self) -> None:
        if not self.game_id or not self.scene_id or not self.target_type:
            raise ValueError("game_id, scene_id, and target_type are required")
        if not 0.0 <= float(self.min_confidence) <= 1.0:
            raise ValueError("min_confidence must be between 0 and 1")
        if int(self.confirmation_frames) < 1:
            raise ValueError("confirmation_frames must be at least 1")
        algorithms = tuple(self.algorithms)
        instance_ids = [item.instance_id for item in algorithms]
        if len(instance_ids) != len(set(instance_ids)):
            raise ValueError("algorithm instance_id values must be unique")
        selection_strategy = str(self.selection_strategy or "confidence").strip().lower()
        if selection_strategy not in SUPPORTED_SELECTION_STRATEGIES:
            supported = ", ".join(sorted(SUPPORTED_SELECTION_STRATEGIES))
            raise ValueError(f"selection_strategy must be one of: {supported}")
        object.__setattr__(self, "algorithms", algorithms)
        object.__setattr__(self, "selection_strategy", selection_strategy)
        object.__setattr__(self, "metadata", dict(self.metadata))

    def copy(self) -> "TargetProfile":
        return deepcopy(self)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": int(self.schema_version),
            "game_id": self.game_id,
            "scene_id": self.scene_id,
            "target_type": self.target_type,
            "algorithms": [item.to_dict() for item in self.algorithms],
            "min_confidence": float(self.min_confidence),
            "confirmation_frames": int(self.confirmation_frames),
            "selection_strategy": self.selection_strategy,
            "metadata": deepcopy(self.metadata),
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "TargetProfile":
        version = int(payload.get("schema_version", 1))
        if version != 1:
            raise ValueError(f"unsupported perception profile schema version: {version}")
        algorithms = tuple(
            AlgorithmProfile.from_dict(item)
            for item in (payload.get("algorithms") or [])
        )
        return cls(
            game_id=str(payload.get("game_id", "")),
            scene_id=str(payload.get("scene_id", "")),
            target_type=str(payload.get("target_type", "")),
            algorithms=algorithms,
            min_confidence=float(payload.get("min_confidence", 0.5)),
            confirmation_frames=int(payload.get("confirmation_frames", 1)),
            selection_strategy=str(payload.get("selection_strategy", "confidence")),
            metadata=dict(payload.get("metadata") or {}),
            schema_version=version,
        )
