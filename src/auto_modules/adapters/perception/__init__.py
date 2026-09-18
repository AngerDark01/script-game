"""Concrete perception provider implementations."""

from .rapidocr import RAPIDOCR_PROVIDER_ID, RapidOcrProvider
from .rapidocr_models import (
    RAPIDOCR_PPOCR_V6_MULTILINGUAL_SMALL,
    RapidOcrModelSpec,
    get_rapidocr_model_spec,
    list_rapidocr_model_specs,
    resolve_rapidocr_engine_options,
    verify_rapidocr_model_file,
)

__all__ = [
    "RAPIDOCR_PROVIDER_ID",
    "RAPIDOCR_PPOCR_V6_MULTILINGUAL_SMALL",
    "RapidOcrModelSpec",
    "RapidOcrProvider",
    "get_rapidocr_model_spec",
    "list_rapidocr_model_specs",
    "resolve_rapidocr_engine_options",
    "verify_rapidocr_model_file",
]
