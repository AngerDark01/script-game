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
from .rapidocr_models import (
    RAPIDOCR_PPOCR_V6_MULTILINGUAL_SMALL,
    RapidOcrModelSpec,
    get_rapidocr_model_spec,
    list_rapidocr_model_specs,
    resolve_rapidocr_engine_options,
    verify_rapidocr_model_file,
)
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
    "RAPIDOCR_PPOCR_V6_MULTILINGUAL_SMALL",
    "RapidOcrProvider",
    "RapidOcrModelSpec",
    "TemplateResource",
    "TemplateResourceProvider",
    "UnknownProviderError",
    "get_rapidocr_model_spec",
    "list_rapidocr_model_specs",
    "resolve_rapidocr_engine_options",
    "verify_rapidocr_model_file",
]
