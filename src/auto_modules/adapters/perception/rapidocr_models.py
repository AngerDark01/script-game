"""Named, locally verified RapidOCR recognition-model resources.

This module deliberately contains metadata and local-file validation only.  It
does not import RapidOCR, download a model, recognize text, or contain target
or game semantics.  Application composition resolves an installed model to a
fresh ``engine_options`` mapping and passes that mapping to ``RapidOcrProvider``.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any, Mapping

from auto_modules.core.perception.providers.contracts import ProviderUnavailableError


RAPIDOCR_PPOCR_V6_MULTILINGUAL_SMALL = "rapidocr.ppocr-v6-multilingual-small"

_DEFAULT_ENGINE_OPTIONS: Mapping[str, Any] = MappingProxyType(
    {
        "intra_op_num_threads": 4,
        "inter_op_num_threads": 1,
    }
)


@dataclass(frozen=True)
class RapidOcrModelSpec:
    """A downloadable recognition-model asset with its integrity contract."""

    model_id: str
    display_name: str
    description: str
    file_name: str
    download_url: str
    sha256: str
    recommended_engine_options: Mapping[str, Any] = _DEFAULT_ENGINE_OPTIONS

    def __post_init__(self) -> None:
        for field_name in ("model_id", "display_name", "description", "file_name", "download_url", "sha256"):
            value = getattr(self, field_name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"RapidOCR model {field_name} must be a non-empty string")
        if Path(self.file_name).name != self.file_name:
            raise ValueError("RapidOCR model file_name must not include a directory")
        normalized_hash = self.sha256.lower()
        if len(normalized_hash) != 64 or any(character not in "0123456789abcdef" for character in normalized_hash):
            raise ValueError("RapidOCR model sha256 must be a 64-character hexadecimal digest")
        if not isinstance(self.recommended_engine_options, Mapping):
            raise TypeError("RapidOCR model recommended_engine_options must be a mapping")


_MODEL_SPECS: Mapping[str, RapidOcrModelSpec] = MappingProxyType(
    {
        RAPIDOCR_PPOCR_V6_MULTILINGUAL_SMALL: RapidOcrModelSpec(
            model_id=RAPIDOCR_PPOCR_V6_MULTILINGUAL_SMALL,
            display_name="PP-OCRv6 multilingual small",
            description=(
                "Compact multilingual recognition model with Simplified Chinese and "
                "Traditional Chinese coverage for local RapidOCR text localization."
            ),
            file_name="PP-OCRv6_rec_small.onnx",
            download_url=(
                "https://www.modelscope.cn/models/RapidAI/RapidOCR/resolve/v3.9.2/"
                "onnx/PP-OCRv6/rec/PP-OCRv6_rec_small.onnx"
            ),
            sha256="6f327246b50388f3c176ae304bd95767ea6dc0c9ae92153ef8cbe210b3c14884",
        ),
    }
)


def list_rapidocr_model_specs() -> tuple[RapidOcrModelSpec, ...]:
    """Return the stable model catalog in declaration order without I/O."""
    return tuple(_MODEL_SPECS.values())


def get_rapidocr_model_spec(model_id: str) -> RapidOcrModelSpec:
    """Resolve one catalog ID or fail as a configuration error before inference."""
    if not isinstance(model_id, str) or not model_id.strip():
        raise ValueError("RapidOCR model_id must be a non-empty string")
    try:
        return _MODEL_SPECS[model_id]
    except KeyError as exc:
        known_models = ", ".join(_MODEL_SPECS)
        raise ValueError(f"unknown RapidOCR model {model_id!r}; available: {known_models}") from exc


def verify_rapidocr_model_file(spec: RapidOcrModelSpec, model_path: str | Path) -> Path:
    """Return an absolute asset path only after its declared SHA-256 matches."""
    if not isinstance(spec, RapidOcrModelSpec):
        raise TypeError("spec must be a RapidOcrModelSpec")
    try:
        resolved_path = Path(model_path).expanduser().resolve()
    except (TypeError, OSError) as exc:
        raise ValueError("RapidOCR model_path must be a valid local path") from exc
    if not resolved_path.is_file():
        raise ProviderUnavailableError(_missing_model_message(spec, resolved_path.parent))
    try:
        actual_digest = _sha256_file(resolved_path)
    except OSError as exc:
        raise ProviderUnavailableError(f"RapidOCR model {spec.model_id!r} could not be read: {exc}") from exc
    if actual_digest != spec.sha256.lower():
        raise ProviderUnavailableError(
            f"RapidOCR model {spec.model_id!r} checksum mismatch at {resolved_path}. "
            "Reinstall the model before using it."
        )
    return resolved_path


def resolve_rapidocr_engine_options(
    model_id: str,
    model_directory: str | Path,
    *,
    overrides: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build copied ``RapidOcrProvider.engine_options`` for one verified model.

    Callers can tune normal RapidOCR construction options, such as thread counts
    or detection dimensions, through ``overrides``.  ``rec_model_path`` is
    protected because changing it would bypass the selected resource's checksum.
    """
    spec = get_rapidocr_model_spec(model_id)
    if overrides is not None and not isinstance(overrides, Mapping):
        raise TypeError("RapidOCR model overrides must be a mapping")
    safe_overrides = dict(overrides or {})
    if "rec_model_path" in safe_overrides:
        raise ValueError("rec_model_path is owned by the selected RapidOCR model resource")
    try:
        candidate_path = Path(model_directory).expanduser() / spec.file_name
    except TypeError as exc:
        raise ValueError("RapidOCR model_directory must be a valid local path") from exc
    verified_path = verify_rapidocr_model_file(spec, candidate_path)
    engine_options = dict(spec.recommended_engine_options)
    engine_options.update(safe_overrides)
    engine_options["rec_model_path"] = str(verified_path)
    return engine_options


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _missing_model_message(spec: RapidOcrModelSpec, directory: Path) -> str:
    command = (
        "python tools/probes/install_perception_ocr_model.py "
        f"--model {spec.model_id} --destination {directory}"
    )
    return f"RapidOCR model {spec.model_id!r} is not installed. Install it with: {command}"
