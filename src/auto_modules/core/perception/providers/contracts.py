from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping, Protocol

from ..models import BoundingBox, CoordinateSpace, FrameContext


class ProviderCapability(str, Enum):
    """Kinds of raw data or backend evidence a provider can supply."""

    FRAME_SOURCE = "frame_source"
    TEMPLATE_RESOURCE = "template_resource"
    OCR = "ocr"
    FEATURE_BACKEND = "feature_backend"


_PROVIDER_STATUSES = {"available", "experimental", "unavailable"}


class ProviderError(RuntimeError):
    """Base error for provider registration and resolution failures."""


class ProviderRegistrationError(ProviderError):
    """Raised when a provider descriptor and implementation are incompatible."""


class UnknownProviderError(ProviderError):
    """Raised when the requested provider ID has no registered descriptor."""


class ProviderCapabilityMismatchError(ProviderError):
    """Raised when a known provider does not offer the requested capability."""


class ProviderUnavailableError(ProviderError):
    """Raised when a discoverable provider has no runnable implementation."""


@dataclass(frozen=True)
class ProviderDescriptor:
    """Discoverable configuration metadata for a raw-data provider."""

    provider_id: str
    display_name: str
    capability: ProviderCapability
    description: str = ""
    status: str = "available"
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        provider_id = str(self.provider_id).strip()
        display_name = str(self.display_name).strip()
        if not provider_id or not display_name:
            raise ValueError("provider_id and display_name are required")
        try:
            capability = ProviderCapability(self.capability)
        except ValueError as exc:
            raise ValueError(f"unsupported provider capability: {self.capability}") from exc
        status = str(self.status).strip().lower()
        if status not in _PROVIDER_STATUSES:
            raise ValueError(f"unsupported provider status: {self.status}")
        object.__setattr__(self, "provider_id", provider_id)
        object.__setattr__(self, "display_name", display_name)
        object.__setattr__(self, "capability", capability)
        object.__setattr__(self, "status", status)
        object.__setattr__(self, "metadata", dict(self.metadata))

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider_id": self.provider_id,
            "display_name": self.display_name,
            "capability": self.capability.value,
            "description": self.description,
            "status": self.status,
            "metadata": deepcopy(dict(self.metadata)),
        }


@dataclass(frozen=True)
class TemplateResource:
    """A provider-resolved template asset, not a template-match result."""

    resource_id: str
    image: Any
    source: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        resource_id = str(self.resource_id).strip()
        if not resource_id:
            raise ValueError("resource_id is required")
        if self.image is None:
            raise ValueError("template resource image must not be None")
        object.__setattr__(self, "resource_id", resource_id)
        object.__setattr__(self, "metadata", dict(self.metadata))


@dataclass(frozen=True)
class OcrSpan:
    """One text span and geometry returned by an OCR provider."""

    text: str
    bbox: BoundingBox
    coordinate_space: CoordinateSpace
    confidence: float
    language: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not str(self.text):
            raise ValueError("OCR text must not be empty")
        if not isinstance(self.bbox, BoundingBox):
            raise TypeError("OCR bbox must be a BoundingBox")
        if not isinstance(self.coordinate_space, CoordinateSpace):
            raise TypeError("OCR coordinate_space must be a CoordinateSpace")
        if not 0.0 <= float(self.confidence) <= 1.0:
            raise ValueError("OCR confidence must be between 0 and 1")
        object.__setattr__(self, "metadata", dict(self.metadata))


@dataclass(frozen=True)
class FeatureMatch:
    """Raw local-feature correspondence awaiting algorithm-level interpretation."""

    resource_id: str
    frame_point: tuple[float, float]
    resource_point: tuple[float, float]
    confidence: float
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        resource_id = str(self.resource_id).strip()
        if not resource_id:
            raise ValueError("resource_id is required")
        if len(self.frame_point) != 2 or len(self.resource_point) != 2:
            raise ValueError("feature points must contain exactly two coordinates")
        if not 0.0 <= float(self.confidence) <= 1.0:
            raise ValueError("feature confidence must be between 0 and 1")
        object.__setattr__(self, "resource_id", resource_id)
        object.__setattr__(self, "metadata", dict(self.metadata))


class FrameSource(Protocol):
    """Captures one normalized image frame without detecting a target."""

    def capture(self) -> FrameContext: ...


class TemplateResourceProvider(Protocol):
    """Loads template assets by stable resource ID."""

    def load(self, resource_id: str) -> TemplateResource: ...


class OcrProvider(Protocol):
    """Returns OCR spans for one frame using provider-specific parameters."""

    def recognize(self, frame: FrameContext, parameters: Mapping[str, Any] | None = None) -> tuple[OcrSpan, ...]: ...


class FeatureBackend(Protocol):
    """Returns feature correspondences for a frame and resolved resource."""

    def match(
        self,
        frame: FrameContext,
        resource: TemplateResource,
        parameters: Mapping[str, Any] | None = None,
    ) -> tuple[FeatureMatch, ...]: ...
