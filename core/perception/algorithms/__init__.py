"""Algorithm descriptors and reusable detector implementations."""

from .base import AlgorithmDescriptor, ParameterSpec
from .color import ColorRegionDetector
from .ocr_adapter import ProviderBackedOcrDetector
from .template import TemplateDetector
from .template_adapter import ProviderBackedTemplateDetector

__all__ = [
    "AlgorithmDescriptor",
    "ParameterSpec",
    "ColorRegionDetector",
    "ProviderBackedOcrDetector",
    "TemplateDetector",
    "ProviderBackedTemplateDetector",
]
