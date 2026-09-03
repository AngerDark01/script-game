"""Provider contracts for raw perception inputs and backend evidence."""

from .contracts import (
    FeatureBackend,
    FeatureMatch,
    FrameSource,
    OcrProvider,
    OcrSpan,
    ProviderCapability,
    ProviderCapabilityMismatchError,
    ProviderDescriptor,
    ProviderError,
    ProviderRegistrationError,
    ProviderUnavailableError,
    TemplateResource,
    TemplateResourceProvider,
    UnknownProviderError,
)
from .builtins import create_default_provider_registry
from .rapidocr import RAPIDOCR_PROVIDER_ID, RapidOcrProvider
from .registry import ProviderRegistry

__all__ = [
    "FeatureBackend",
    "FeatureMatch",
    "FrameSource",
    "create_default_provider_registry",
    "OcrProvider",
    "OcrSpan",
    "ProviderCapability",
    "ProviderCapabilityMismatchError",
    "ProviderDescriptor",
    "ProviderError",
    "ProviderRegistrationError",
    "ProviderRegistry",
    "ProviderUnavailableError",
    "RAPIDOCR_PROVIDER_ID",
    "RapidOcrProvider",
    "TemplateResource",
    "TemplateResourceProvider",
    "UnknownProviderError",
]
