"""Explicit installer for checksum-verified local perception OCR assets."""

from __future__ import annotations

import argparse
import os
import sys
import tempfile
from pathlib import Path
from typing import Callable, Protocol
from urllib.request import urlopen

# This file is also a directly executable utility.  Python otherwise places
# only ``tools/probes/`` on sys.path; the production package lives under
# ``src/auto_modules/`` and is added explicitly below.
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(_PROJECT_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT / "src"))

from auto_modules.core.perception.providers.contracts import ProviderUnavailableError
from auto_modules.adapters.perception.rapidocr_models import (
    RapidOcrModelSpec,
    get_rapidocr_model_spec,
    list_rapidocr_model_specs,
    verify_rapidocr_model_file,
)


class _ReadableResponse(Protocol):
    def read(self, size: int = -1) -> bytes: ...

    def close(self) -> object: ...


_DEFAULT_TIMEOUT_SECONDS = 60.0
_DOWNLOAD_CHUNK_BYTES = 1024 * 1024


def install_rapidocr_model(
    model_id: str,
    destination: str | Path,
    *,
    timeout_seconds: float = _DEFAULT_TIMEOUT_SECONDS,
    opener: Callable[..., _ReadableResponse] = urlopen,
) -> Path:
    """Download one model to a temporary file, validate it, then atomically install it.

    A valid existing file is returned immediately.  If an existing file is
    corrupt, it remains in place until a fully downloaded replacement passes the
    manifest checksum.  This function does not run during normal application
    import or inference; users invoke it explicitly from the CLI or tooling.
    """
    spec = get_rapidocr_model_spec(model_id)
    timeout = _validate_timeout(timeout_seconds)
    try:
        destination_path = Path(destination).expanduser().resolve()
    except (TypeError, OSError) as exc:
        raise ValueError("destination must be a valid local path") from exc
    destination_path.mkdir(parents=True, exist_ok=True)
    if not destination_path.is_dir():
        raise ValueError(f"destination must be a directory: {destination_path}")
    final_path = destination_path / spec.file_name
    if final_path.is_file():
        try:
            return verify_rapidocr_model_file(spec, final_path)
        except ProviderUnavailableError:
            pass
    elif final_path.exists():
        raise ProviderUnavailableError(f"RapidOCR model destination is not a file: {final_path}")

    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb",
            prefix=f".{spec.file_name}.",
            suffix=".part",
            dir=destination_path,
            delete=False,
        ) as temporary_file:
            temporary_path = Path(temporary_file.name)
            _copy_download(spec, temporary_file, opener=opener, timeout_seconds=timeout)
        verify_rapidocr_model_file(spec, temporary_path)
        os.replace(temporary_path, final_path)
        temporary_path = None
        return verify_rapidocr_model_file(spec, final_path)
    except ProviderUnavailableError:
        raise
    except Exception as exc:
        raise ProviderUnavailableError(f"RapidOCR model download failed for {spec.model_id!r}: {exc}") from exc
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


def _copy_download(
    spec: RapidOcrModelSpec,
    destination_stream: object,
    *,
    opener: Callable[..., _ReadableResponse],
    timeout_seconds: float,
) -> None:
    response = opener(spec.download_url, timeout=timeout_seconds)
    try:
        while chunk := response.read(_DOWNLOAD_CHUNK_BYTES):
            if not isinstance(chunk, bytes):
                raise TypeError("model downloader returned a non-bytes chunk")
            destination_stream.write(chunk)  # type: ignore[attr-defined]
    finally:
        response.close()


def _validate_timeout(timeout_seconds: float) -> float:
    try:
        timeout = float(timeout_seconds)
    except (TypeError, ValueError) as exc:
        raise ValueError("timeout_seconds must be a positive number") from exc
    if timeout <= 0:
        raise ValueError("timeout_seconds must be a positive number")
    return timeout


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Install a checksum-verified RapidOCR perception model.")
    parser.add_argument("--model", required=True, choices=[spec.model_id for spec in list_rapidocr_model_specs()])
    parser.add_argument("--destination", required=True, help="Local directory for the downloaded ONNX model")
    parser.add_argument("--timeout", type=float, default=_DEFAULT_TIMEOUT_SECONDS, help="Download timeout in seconds")
    return parser


def main() -> int:
    arguments = _build_parser().parse_args()
    installed_path = install_rapidocr_model(
        arguments.model,
        arguments.destination,
        timeout_seconds=arguments.timeout,
    )
    print(f"Installed {arguments.model} at {installed_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
