"""Safe composition proof from OCR text detection to one mapped pointer action."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from core.actions import ActionKind, ActionRequest, ActionResult
from core.perception.algorithms.ocr_adapter import ProviderBackedOcrDetector
from core.perception.models import FrameContext, TargetDetection
from core.perception.providers import OcrProvider
from core.spatial import DesktopCoordinateMapper, MappedPoint, Point2D, ScreenGeometry


class DesktopFrameProvider(Protocol):
    """Capture a desktop frame together with the physical geometry it represents."""

    def capture(self) -> tuple[FrameContext, ScreenGeometry]: ...


class MappedActionAdapter(Protocol):
    """Execute a generic action request after workflow safety gates succeed."""

    def execute(self, request: ActionRequest) -> ActionResult: ...


@dataclass(frozen=True)
class DesktopProofReport:
    """Complete observable result of one desktop OCR-to-action proof run."""

    status: str
    frame_size: tuple[int, int]
    geometry: ScreenGeometry
    detection: TargetDetection | None
    mapped_point: MappedPoint | None
    action_result: ActionResult | None
    reason: str | None = None


class DesktopOcrActionProof:
    """Compose injected capture, OCR, mapping, and action capabilities safely."""

    def __init__(
        self,
        *,
        frame_source: DesktopFrameProvider,
        ocr_provider: OcrProvider,
        action_adapter: MappedActionAdapter,
        min_confidence: float = 0.8,
        double_click_interval_ms: int = 80,
        target_type: str = "desktop_text",
    ) -> None:
        if not 0.0 <= float(min_confidence) <= 1.0:
            raise ValueError("min_confidence must be between 0 and 1")
        if not isinstance(double_click_interval_ms, int) or double_click_interval_ms < 0:
            raise ValueError("double_click_interval_ms must be a non-negative integer")
        if not target_type.strip():
            raise ValueError("target_type must not be empty")
        self._frame_source = frame_source
        self._ocr_provider = ocr_provider
        self._action_adapter = action_adapter
        self._min_confidence = float(min_confidence)
        self._double_click_interval_ms = double_click_interval_ms
        self._target_type = target_type

    def run(self, *, target_text: str, execute: bool = False) -> DesktopProofReport:
        """Find one exact label, map its center, and optionally perform one double click."""
        if not isinstance(target_text, str) or not target_text.strip():
            raise ValueError("target_text must be a non-empty string")
        frame, geometry = self._frame_source.capture()
        frame_size = _frame_size(frame)
        detector = ProviderBackedOcrDetector(
            target_type=self._target_type,
            provider=self._ocr_provider,
            parameters={
                "text_query": target_text,
                "match_mode": "exact",
                "case_sensitive": True,
                "min_ocr_confidence": self._min_confidence,
            },
        )
        detections = detector.detect(frame)
        if not detections:
            return DesktopProofReport("not_found", frame_size, geometry, None, None, None, "no exact OCR match")
        if len(detections) != 1:
            return DesktopProofReport(
                "ambiguous",
                frame_size,
                geometry,
                None,
                None,
                None,
                f"expected one exact OCR match but found {len(detections)}",
            )
        detection = detections[0]
        try:
            mapper = DesktopCoordinateMapper(source_size=frame_size, destination=geometry)
            mapped_point = mapper.map_point(Point2D(*detection.center), detection.coordinate_space)
        except (TypeError, ValueError) as exc:
            return DesktopProofReport("rejected", frame_size, geometry, detection, None, None, str(exc))
        if not execute:
            return DesktopProofReport("dry_run", frame_size, geometry, detection, mapped_point, None)
        action_result = self._action_adapter.execute(
            ActionRequest(
                kind=ActionKind.DOUBLE_CLICK,
                point=mapped_point,
                interval_ms=self._double_click_interval_ms,
            )
        )
        return DesktopProofReport("executed", frame_size, geometry, detection, mapped_point, action_result)


def _frame_size(frame: FrameContext) -> tuple[int, int]:
    if not isinstance(frame, FrameContext):
        raise TypeError("frame_source must return a FrameContext")
    width, height = frame.size
    if width is None or height is None or width <= 0 or height <= 0:
        raise ValueError("desktop frame must declare positive width and height")
    return int(width), int(height)
