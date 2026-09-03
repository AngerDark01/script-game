from __future__ import annotations

from typing import Any, Mapping

from ..models import FrameContext, TargetDetection
from ..providers import TemplateResource, TemplateResourceProvider
from .template import TemplateDetector


class ProviderBackedTemplateDetector:
    """Resolve one template resource, then delegate matching to ``TemplateDetector``."""

    algorithm_id = "template"

    def __init__(
        self,
        *,
        target_type: str,
        provider: TemplateResourceProvider,
        resource_id: str,
        parameters: Mapping[str, Any] | None = None,
    ) -> None:
        normalized_id = str(resource_id).strip()
        if not normalized_id:
            raise ValueError("resource_id is required")
        load = getattr(provider, "load", None)
        if not callable(load):
            raise TypeError("template provider must expose load(resource_id)")
        resource = load(normalized_id)
        if not isinstance(resource, TemplateResource):
            raise TypeError("template provider must return a TemplateResource")
        self.target_type = target_type
        self.provider = provider
        self.resource_id = normalized_id
        self.resource = resource
        self.detector = TemplateDetector(
            target_type=target_type,
            template=resource.image,
            parameters=parameters,
        )

    def detect(self, frame: FrameContext) -> list[TargetDetection]:
        """Return the unchanged detector output for the resolved resource."""
        return self.detector.detect(frame)
