from __future__ import annotations

import re
from typing import Any, Mapping

from ..models import DetectionEvidence, FrameContext, TargetDetection
from ..providers import OcrProvider, OcrSpan


class ProviderBackedOcrDetector:
    """Convert raw OCR spans from one explicit provider into target detections."""

    algorithm_id = "ocr"

    def __init__(
        self,
        *,
        target_type: str,
        provider: OcrProvider,
        parameters: Mapping[str, Any] | None = None,
    ) -> None:
        recognize = getattr(provider, "recognize", None)
        if not callable(recognize):
            raise TypeError("OCR provider must expose recognize(frame, parameters=None)")
        values = dict(parameters or {})
        query = str(values.pop("text_query", "")).strip()
        if not query:
            raise ValueError("text_query is required")
        match_mode = str(values.pop("match_mode", "exact")).strip().lower()
        if match_mode not in {"exact", "contains", "regex"}:
            raise ValueError(f"unsupported OCR match_mode: {match_mode}")
        provider_parameters = values.pop("provider_parameters", {})
        if not isinstance(provider_parameters, Mapping):
            raise TypeError("provider_parameters must be a mapping")

        self.target_type = str(target_type)
        self.provider = provider
        self._recognize = recognize
        self.text_query = query
        self.match_mode = match_mode
        self.case_sensitive = bool(values.pop("case_sensitive", False))
        self.min_ocr_confidence = float(values.pop("min_ocr_confidence", 0.0))
        if not 0.0 <= self.min_ocr_confidence <= 1.0:
            raise ValueError("min_ocr_confidence must be between 0 and 1")
        raw_max_results = values.pop("max_results", None)
        self.max_results = None if raw_max_results is None else int(raw_max_results)
        if self.max_results is not None and self.max_results < 0:
            raise ValueError("max_results must be zero or a positive integer")
        if self.max_results == 0:
            self.max_results = None
        self.provider_parameters = dict(provider_parameters)
        if self.match_mode == "regex":
            try:
                self._regex = re.compile(self.text_query, 0 if self.case_sensitive else re.IGNORECASE)
            except re.error as exc:
                raise ValueError(f"invalid OCR regex: {self.text_query}") from exc
        else:
            self._regex = None

    def detect(self, frame: FrameContext) -> list[TargetDetection]:
        """Recognize one frame and normalize matching spans without remapping geometry."""
        spans = tuple(self._recognize(frame, dict(self.provider_parameters)))
        detections: list[TargetDetection] = []
        for span in spans:
            if not isinstance(span, OcrSpan):
                raise TypeError("OCR provider output must contain OcrSpan values")
            if span.confidence < self.min_ocr_confidence or not self._matches(span.text):
                continue
            evidence_details = {
                "query": self.text_query,
                "match_mode": self.match_mode,
                "case_sensitive": self.case_sensitive,
                "language": span.language,
                **dict(span.metadata),
            }
            detections.append(
                TargetDetection(
                    target_type=self.target_type,
                    center=span.bbox.center,
                    coordinate_space=span.coordinate_space,
                    confidence=span.confidence,
                    bbox=span.bbox,
                    source=self.algorithm_id,
                    detected_at_ms=frame.captured_at_ms,
                    text=span.text,
                    evidence=(DetectionEvidence(self.algorithm_id, span.confidence, evidence_details),),
                )
            )
        detections.sort(key=lambda item: item.confidence, reverse=True)
        return detections if self.max_results is None else detections[: self.max_results]

    def _matches(self, text: str) -> bool:
        if self._regex is not None:
            return self._regex.search(text) is not None
        candidate = text if self.case_sensitive else text.casefold()
        query = self.text_query if self.case_sensitive else self.text_query.casefold()
        return candidate == query if self.match_mode == "exact" else query in candidate
