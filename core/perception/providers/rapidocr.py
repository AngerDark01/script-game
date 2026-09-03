"""Optional, local RapidOCR backend for geometry-preserving text recognition."""

from __future__ import annotations

from importlib import import_module
from math import ceil, floor, isfinite
from threading import RLock
from typing import Any, Callable, Mapping, Sequence

from ..models import BoundingBox, CoordinateSpace, FrameContext
from .contracts import OcrSpan, ProviderError, ProviderUnavailableError


RAPIDOCR_PROVIDER_ID = "ocr.rapidocr_onnxruntime"


class RapidOcrProvider:
    """Run one cached RapidOCR engine and return full-frame ``OcrSpan`` values.

    The optional package is imported and its ONNX models are initialized only on
    the first ``recognize`` call.  The backend instance is intentionally reused:
    it avoids the substantial process/model startup cost for every captured frame.
    """

    def __init__(
        self,
        *,
        engine_options: Mapping[str, Any] | None = None,
        backend_factory: Callable[[], Any] | None = None,
    ) -> None:
        if engine_options is not None and not isinstance(engine_options, Mapping):
            raise TypeError("engine_options must be a mapping")
        if backend_factory is not None and not callable(backend_factory):
            raise TypeError("backend_factory must be callable")
        self._engine_options = dict(engine_options or {})
        self._backend_factory = backend_factory
        self._backend: Any | None = None
        self._lock = RLock()

    def recognize(
        self,
        frame: FrameContext,
        parameters: Mapping[str, Any] | None = None,
    ) -> tuple[OcrSpan, ...]:
        """Recognize text in a frame or ROI and normalize its quadrilateral boxes.

        ``parameters`` is deliberately per-call and copied before use.  It
        accepts ``roi`` (`BoundingBox`, a four-item sequence, or a mapping with
        ``left/top/width/height``), an optional ``language`` result label, and
        ``backend_options`` forwarded to RapidOCR's call API (for example
        ``use_cls``, ``box_thresh``, or ``text_score``).
        """
        if not isinstance(frame, FrameContext):
            raise TypeError("frame must be a FrameContext")
        values = dict(parameters or {})
        roi = _pop_roi(values)
        language = _pop_language(values)
        backend_options = _pop_backend_options(values)
        if values:
            names = ", ".join(sorted(str(name) for name in values))
            raise ValueError(f"unsupported RapidOCR parameter(s): {names}")

        image, offset, actual_roi = _crop_to_roi(frame.image, roi)
        with self._lock:
            backend = self._get_backend_locked()
            try:
                raw_output = backend(image, **backend_options)
            except ProviderError:
                raise
            except Exception as exc:
                raise ProviderError(f"RapidOCR recognition failed: {exc}") from exc
        raw_spans, elapsed_seconds = _split_backend_output(raw_output)
        if raw_spans is None:
            return ()
        if not _is_sequence(raw_spans):
            raise ProviderError("RapidOCR result rows must be a sequence or None")

        return tuple(
            _to_ocr_span(
                raw_item,
                coordinate_space=frame.coordinate_space,
                offset=offset,
                language=language,
                elapsed_seconds=elapsed_seconds,
                actual_roi=actual_roi,
            )
            for raw_item in raw_spans
        )

    def _get_backend_locked(self) -> Any:
        if self._backend is not None:
            return self._backend
        factory = self._backend_factory or self._create_default_backend
        backend = factory()
        if not callable(backend):
            raise ProviderUnavailableError("RapidOCR backend factory did not return a callable engine")
        self._backend = backend
        return backend

    def _create_default_backend(self) -> Any:
        try:
            module = import_module("rapidocr_onnxruntime")
            rapid_ocr = getattr(module, "RapidOCR")
        except (ImportError, AttributeError) as exc:
            raise ProviderUnavailableError(
                "RapidOCR is unavailable. Install the optional requirements-ocr.txt dependencies."
            ) from exc
        try:
            return rapid_ocr(**self._engine_options)
        except Exception as exc:
            raise ProviderUnavailableError(f"RapidOCR could not initialize: {exc}") from exc


def _pop_roi(values: dict[str, Any]) -> tuple[float, float, float, float] | None:
    if "roi" not in values:
        return None
    raw_roi = values.pop("roi")
    if isinstance(raw_roi, BoundingBox):
        values_to_coerce: Sequence[Any] = (raw_roi.left, raw_roi.top, raw_roi.width, raw_roi.height)
    elif isinstance(raw_roi, Mapping):
        required = ("left", "top", "width", "height")
        missing = [name for name in required if name not in raw_roi]
        if missing:
            raise ValueError(f"RapidOCR ROI is missing: {', '.join(missing)}")
        values_to_coerce = tuple(raw_roi[name] for name in required)
    elif _is_sequence(raw_roi):
        values_to_coerce = raw_roi
    else:
        raise TypeError("RapidOCR ROI must be a BoundingBox, mapping, or four-item sequence")
    if len(values_to_coerce) != 4:
        raise ValueError("RapidOCR ROI must contain left, top, width, and height")
    try:
        left, top, width, height = (float(value) for value in values_to_coerce)
    except (TypeError, ValueError) as exc:
        raise ValueError("RapidOCR ROI coordinates must be numeric") from exc
    if not all(isfinite(value) for value in (left, top, width, height)) or width <= 0 or height <= 0:
        raise ValueError("RapidOCR ROI width and height must be finite positive values")
    return left, top, width, height


def _pop_language(values: dict[str, Any]) -> str | None:
    if "language" not in values:
        return None
    raw_language = values.pop("language")
    if raw_language is None:
        return None
    language = str(raw_language).strip()
    if not language:
        raise ValueError("RapidOCR language must not be empty")
    return language


def _pop_backend_options(values: dict[str, Any]) -> dict[str, Any]:
    raw_options = values.pop("backend_options", {})
    if not isinstance(raw_options, Mapping):
        raise TypeError("RapidOCR backend_options must be a mapping")
    return dict(raw_options)


def _crop_to_roi(
    image: Any,
    roi: tuple[float, float, float, float] | None,
) -> tuple[Any, tuple[float, float], dict[str, int] | None]:
    if roi is None:
        return image, (0.0, 0.0), None
    shape = getattr(image, "shape", None)
    if shape is None or len(shape) < 2:
        raise TypeError("RapidOCR ROI requires an array-like image with at least two dimensions")
    image_height, image_width = int(shape[0]), int(shape[1])
    if image_width <= 0 or image_height <= 0:
        raise ValueError("RapidOCR ROI requires a non-empty image")
    left, top, width, height = roi
    x0 = max(0, floor(left))
    y0 = max(0, floor(top))
    x1 = min(image_width, ceil(left + width))
    y1 = min(image_height, ceil(top + height))
    if x1 <= x0 or y1 <= y0:
        raise ValueError("RapidOCR ROI does not intersect the image")
    try:
        cropped = image[y0:y1, x0:x1]
    except (TypeError, IndexError) as exc:
        raise TypeError("RapidOCR ROI requires an image that supports array slicing") from exc
    return cropped, (float(x0), float(y0)), {"left": x0, "top": y0, "width": x1 - x0, "height": y1 - y0}


def _split_backend_output(raw_output: Any) -> tuple[Any, tuple[float, ...]]:
    if not isinstance(raw_output, tuple) or len(raw_output) != 2:
        raise ProviderError("RapidOCR backend must return (result_rows, elapsed_seconds)")
    raw_spans, raw_elapsed = raw_output
    if raw_elapsed is None:
        return raw_spans, ()
    if not _is_sequence(raw_elapsed):
        raise ProviderError("RapidOCR elapsed_seconds must be a sequence or None")
    try:
        elapsed_seconds = tuple(float(value) for value in raw_elapsed)
    except (TypeError, ValueError) as exc:
        raise ProviderError("RapidOCR elapsed_seconds values must be numeric") from exc
    if not all(isfinite(value) and value >= 0.0 for value in elapsed_seconds):
        raise ProviderError("RapidOCR elapsed_seconds values must be finite and non-negative")
    return raw_spans, elapsed_seconds


def _to_ocr_span(
    raw_item: Any,
    *,
    coordinate_space: CoordinateSpace,
    offset: tuple[float, float],
    language: str | None,
    elapsed_seconds: tuple[float, ...],
    actual_roi: dict[str, int] | None,
) -> OcrSpan:
    if not _is_sequence(raw_item) or len(raw_item) < 3:
        raise ProviderError("each RapidOCR result row must contain polygon, text, and confidence")
    polygon = _normalize_polygon(raw_item[0], offset)
    text = raw_item[1]
    if not isinstance(text, str) or not text.strip():
        raise ProviderError("RapidOCR text must be a non-empty string")
    try:
        confidence = float(raw_item[2])
    except (TypeError, ValueError) as exc:
        raise ProviderError("RapidOCR confidence must be numeric") from exc
    if not isfinite(confidence) or not 0.0 <= confidence <= 1.0:
        raise ProviderError("RapidOCR confidence must be between 0 and 1")
    xs = [point[0] for point in polygon]
    ys = [point[1] for point in polygon]
    left, top, right, bottom = min(xs), min(ys), max(xs), max(ys)
    if right <= left or bottom <= top:
        raise ProviderError("RapidOCR polygon must cover a non-zero area")
    metadata: dict[str, Any] = {
        "provider_id": RAPIDOCR_PROVIDER_ID,
        "polygon": polygon,
        "elapsed_seconds": elapsed_seconds,
    }
    if actual_roi is not None:
        metadata["roi"] = dict(actual_roi)
    return OcrSpan(
        text=text,
        bbox=BoundingBox(left, top, right - left, bottom - top),
        coordinate_space=coordinate_space,
        confidence=confidence,
        language=language,
        metadata=metadata,
    )


def _normalize_polygon(raw_polygon: Any, offset: tuple[float, float]) -> tuple[tuple[float, float], ...]:
    if not _is_sequence(raw_polygon) or len(raw_polygon) < 3:
        raise ProviderError("RapidOCR polygon must contain at least three points")
    offset_x, offset_y = offset
    points: list[tuple[float, float]] = []
    for raw_point in raw_polygon:
        if not _is_sequence(raw_point) or len(raw_point) != 2:
            raise ProviderError("each RapidOCR polygon point must contain exactly two coordinates")
        try:
            x, y = float(raw_point[0]), float(raw_point[1])
        except (TypeError, ValueError) as exc:
            raise ProviderError("RapidOCR polygon coordinates must be numeric") from exc
        if not isfinite(x) or not isfinite(y):
            raise ProviderError("RapidOCR polygon coordinates must be finite")
        points.append((x + offset_x, y + offset_y))
    return tuple(points)


def _is_sequence(value: Any) -> bool:
    return isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray))
