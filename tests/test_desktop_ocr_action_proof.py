import unittest

import numpy as np

from auto_modules.core.perception.models import BoundingBox, CoordinateSpace, FrameContext
from auto_modules.core.perception.providers import OcrSpan
from auto_modules.core.spatial import Point2D, ScreenGeometry
from auto_modules.application.workflows.desktop_ocr_action_proof import DesktopOcrActionProof


class _StaticFrameSource:
    def __init__(self, frame, geometry):
        self.frame = frame
        self.geometry = geometry

    def capture(self):
        return self.frame, self.geometry


class _StaticOcrProvider:
    def __init__(self, spans):
        self.spans = tuple(spans)
        self.calls = []

    def recognize(self, frame, parameters=None):
        self.calls.append((frame, dict(parameters or {})))
        return self.spans


class _RecordingActionAdapter:
    def __init__(self):
        self.requests = []

    def execute(self, request):
        self.requests.append(request)
        raise AssertionError("dry-run must not execute an action")


class DesktopOcrActionProofTests(unittest.TestCase):
    def test_unique_exact_text_returns_mapped_dry_run_report_without_action(self):
        frame = FrameContext(
            image=np.zeros((1080, 1920, 3), dtype=np.uint8),
            width=1920,
            height=1080,
            coordinate_space=CoordinateSpace.FULL_SCREEN,
        )
        geometry = ScreenGeometry(left=0, top=0, width=1920, height=1080)
        provider = _StaticOcrProvider(
            (
                OcrSpan(
                    "\u5922\u4e4b\u5f62",
                    BoundingBox(40, 60, 120, 40),
                    CoordinateSpace.FULL_SCREEN,
                    0.95,
                ),
            )
        )
        actions = _RecordingActionAdapter()
        workflow = DesktopOcrActionProof(
            frame_source=_StaticFrameSource(frame, geometry),
            ocr_provider=provider,
            action_adapter=actions,
            min_confidence=0.8,
        )

        report = workflow.run(target_text="\u5922\u4e4b\u5f62")

        self.assertEqual("dry_run", report.status)
        self.assertEqual((1920, 1080), report.frame_size)
        self.assertEqual((100.0, 80.0), report.detection.center)
        self.assertEqual(Point2D(100.0, 80.0), report.mapped_point.destination_point)
        self.assertIsNone(report.action_result)
        self.assertEqual([], actions.requests)

    def test_multiple_exact_text_hits_refuse_execution_even_when_requested(self):
        frame = FrameContext(
            image=np.zeros((1080, 1920, 3), dtype=np.uint8),
            width=1920,
            height=1080,
            coordinate_space=CoordinateSpace.FULL_SCREEN,
        )
        geometry = ScreenGeometry(left=0, top=0, width=1920, height=1080)
        provider = _StaticOcrProvider(
            (
                OcrSpan("\u5922\u4e4b\u5f62", BoundingBox(40, 60, 120, 40), CoordinateSpace.FULL_SCREEN, 0.95),
                OcrSpan("\u5922\u4e4b\u5f62", BoundingBox(400, 600, 120, 40), CoordinateSpace.FULL_SCREEN, 0.94),
            )
        )
        actions = _RecordingActionAdapter()
        workflow = DesktopOcrActionProof(
            frame_source=_StaticFrameSource(frame, geometry),
            ocr_provider=provider,
            action_adapter=actions,
        )

        report = workflow.run(target_text="\u5922\u4e4b\u5f62", execute=True)

        self.assertEqual("ambiguous", report.status)
        self.assertIsNone(report.mapped_point)
        self.assertIsNone(report.action_result)
        self.assertEqual([], actions.requests)


if __name__ == "__main__":
    unittest.main()
