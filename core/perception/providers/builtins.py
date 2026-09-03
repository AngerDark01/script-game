from __future__ import annotations

from .contracts import ProviderCapability, ProviderDescriptor
from .registry import ProviderRegistry


def create_default_provider_registry() -> ProviderRegistry:
    """Return discoverable provider capabilities without installing runtime backends."""
    registry = ProviderRegistry()
    for descriptor in _default_descriptors():
        registry.register(descriptor, None)
    return registry


def _default_descriptors() -> tuple[ProviderDescriptor, ...]:
    return (
        ProviderDescriptor(
            "frame.screen",
            "Screen frame source",
            ProviderCapability.FRAME_SOURCE,
            "Reserved for an application-provided screen or window capture source.",
            status="unavailable",
        ),
        ProviderDescriptor(
            "template.resource",
            "Template resource provider",
            ProviderCapability.TEMPLATE_RESOURCE,
            "Reserved for an application-provided template asset provider.",
            status="unavailable",
        ),
        ProviderDescriptor(
            "ocr.default",
            "OCR provider",
            ProviderCapability.OCR,
            "Reserved for an optional OCR backend.",
            status="unavailable",
        ),
        ProviderDescriptor(
            "ocr.rapidocr_onnxruntime",
            "RapidOCR (ONNX Runtime)",
            ProviderCapability.OCR,
            "Optional local OCR that returns text polygons for full-frame or ROI recognition.",
            status="unavailable",
            metadata={
                "install_hint": "Install requirements-ocr.txt and compose RapidOcrProvider at runtime.",
                "package": "rapidocr-onnxruntime",
            },
        ),
        ProviderDescriptor(
            "feature.default",
            "Feature backend",
            ProviderCapability.FEATURE_BACKEND,
            "Reserved for an optional local-feature backend.",
            status="unavailable",
        ),
    )
