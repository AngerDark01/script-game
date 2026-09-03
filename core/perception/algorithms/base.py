from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any, Mapping

from ..models import CoordinateSpace


_PARAMETER_KINDS = {"bool", "choice", "float", "int", "path", "text"}
_ALGORITHM_STATUSES = {"available", "experimental", "unavailable"}


@dataclass(frozen=True)
class ParameterSpec:
    """Data-only parameter metadata that a GUI can turn into an editor."""

    name: str
    label: str
    kind: str
    default: Any = None
    minimum: float | int | None = None
    maximum: float | int | None = None
    choices: tuple[Any, ...] = ()
    description: str = ""

    def __post_init__(self) -> None:
        if not self.name or not self.label:
            raise ValueError("parameter name and label are required")
        if self.kind not in _PARAMETER_KINDS:
            raise ValueError(f"unsupported parameter kind: {self.kind}")
        if self.minimum is not None and self.maximum is not None and self.minimum > self.maximum:
            raise ValueError("parameter minimum must not exceed maximum")
        if self.kind in {"int", "float"}:
            if self.minimum is not None and self.default < self.minimum:
                raise ValueError("parameter default is below minimum")
            if self.maximum is not None and self.default > self.maximum:
                raise ValueError("parameter default is above maximum")
        if self.kind == "choice" and self.choices and self.default not in self.choices:
            raise ValueError("choice parameter default must be one of choices")
        object.__setattr__(self, "choices", tuple(self.choices))

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "label": self.label,
            "kind": self.kind,
            "default": deepcopy(self.default),
            "minimum": self.minimum,
            "maximum": self.maximum,
            "choices": list(self.choices),
            "description": self.description,
        }


@dataclass(frozen=True)
class AlgorithmDescriptor:
    """Stable metadata for one algorithm implementation or extension point."""

    algorithm_id: str
    display_name: str
    description: str = ""
    supported_spaces: tuple[CoordinateSpace, ...] = ()
    parameters: tuple[ParameterSpec, ...] = ()
    status: str = "available"
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.algorithm_id or not self.display_name:
            raise ValueError("algorithm_id and display_name are required")
        if self.status not in _ALGORITHM_STATUSES:
            raise ValueError(f"unsupported algorithm status: {self.status}")
        names = [item.name for item in self.parameters]
        if len(names) != len(set(names)):
            raise ValueError("algorithm parameter names must be unique")
        object.__setattr__(self, "supported_spaces", tuple(self.supported_spaces))
        object.__setattr__(self, "parameters", tuple(self.parameters))
        object.__setattr__(self, "metadata", dict(self.metadata))

    def to_dict(self) -> dict[str, Any]:
        return {
            "algorithm_id": self.algorithm_id,
            "display_name": self.display_name,
            "description": self.description,
            "supported_spaces": [space.value for space in self.supported_spaces],
            "parameters": [parameter.to_dict() for parameter in self.parameters],
            "status": self.status,
            "metadata": deepcopy(dict(self.metadata)),
        }
