import importlib.util
import unittest
from unittest.mock import patch

from core.perception.algorithms.ocr_adapter import ProviderBackedOcrDetector
from core.perception.models import BoundingBox, CoordinateSpace, FrameContext
from core.perception.providers import ProviderError, ProviderUnavailableError
from core.perception.providers.rapidocr import RapidOcrProvider


class FakeRapidOcrBackend:
    def __init__(self, output):
        self.output = output
        self.calls = []

    def __call__(self, image, **kwargs):
        self.calls.append((image, dict(kwargs)))
        return self.output


class RapidOcrProviderTests(unittest.TestCase):
    def test_lazy_backend_normalizes_polygon_and_preserves_adapter_chain(self):
        backend = FakeRapidOcrBackend(
            (
                [
                    [
                        [[12, 18], [52, 18], [52, 30], [12, 30]],
                        "Enter Portal",
                        0.93,
                    ]
                ],
                [0.004, 0.001, 0.006],
            )
        )
        factories = []

        def build_backend():
            factories.append("created")
            return backend

        provider = RapidOcrProvider(backend_factory=build_backend)
        self.assertEqual([], factories)

        frame = FrameContext(
            image=object(),
            captured_at_ms=456,
            coordinate_space=CoordinateSpace.GAME_WINDOW,
        )
        provider_parameters = {"language": "en", "backend_options": {"use_cls": False}}
        spans = provider.recognize(
            frame,
            provider_parameters,
        )

        self.assertEqual(["created"], factories)
        self.assertEqual([(frame.image, {"use_cls": False})], backend.calls)
        self.assertEqual(1, len(spans))
        self.assertEqual("Enter Portal", spans[0].text)
        self.assertEqual(BoundingBox(12.0, 18.0, 40.0, 12.0), spans[0].bbox)
        self.assertEqual(CoordinateSpace.GAME_WINDOW, spans[0].coordinate_space)
        self.assertEqual(0.93, spans[0].confidence)
        self.assertEqual("en", spans[0].language)
        self.assertEqual((0.004, 0.001, 0.006), spans[0].metadata["elapsed_seconds"])
        self.assertEqual("ocr.rapidocr_onnxruntime", spans[0].metadata["provider_id"])
        self.assertEqual({"language": "en", "backend_options": {"use_cls": False}}, provider_parameters)

        detector = ProviderBackedOcrDetector(
            target_type="portal_entry",
            provider=provider,
            parameters={"text_query": "enter portal", "match_mode": "exact"},
        )
        detection = detector.detect(frame)[0]

        self.assertEqual("portal_entry", detection.target_type)
        self.assertEqual((32.0, 24.0), detection.center)
        self.assertEqual(456, detection.detected_at_ms)
        self.assertEqual("Enter Portal", detection.text)
        self.assertEqual("ocr", detection.source)
        self.assertEqual(["created"], factories)
        self.assertEqual((frame.image, {}), backend.calls[1])

    def test_roi_is_cropped_and_local_polygon_is_mapped_to_full_frame(self):
        try:
            import numpy as np
        except ImportError as exc:  # pragma: no cover - base runtime already uses NumPy.
            self.fail(f"NumPy is required for the ROI contract test: {exc}")
        backend = FakeRapidOcrBackend(
            (
                [[[[1, 2], [13, 2], [13, 10], [1, 10]], "Tier 15", 0.88]],
                [0.02, 0.01, 0.03],
            )
        )
        provider = RapidOcrProvider(backend_factory=lambda: backend)
        image = np.zeros((120, 240, 3), dtype=np.uint8)
        frame = FrameContext(image=image, coordinate_space=CoordinateSpace.FULL_SCREEN)

        span = provider.recognize(frame, {"roi": {"left": 50, "top": 30, "width": 80, "height": 40}})[0]

        self.assertEqual((40, 80, 3), backend.calls[0][0].shape)
        self.assertEqual(BoundingBox(51.0, 32.0, 12.0, 8.0), span.bbox)
        self.assertEqual(
            {"left": 50, "top": 30, "width": 80, "height": 40},
            span.metadata["roi"],
        )

    def test_malformed_backend_data_and_bad_provider_parameters_fail_explicitly(self):
        malformed = RapidOcrProvider(backend_factory=lambda: FakeRapidOcrBackend(([[["not-a-polygon", "Text", 0.9]]], [0.1])))
        with self.assertRaises(ProviderError):
            malformed.recognize(FrameContext(image=object()))

        provider = RapidOcrProvider(backend_factory=lambda: FakeRapidOcrBackend((None, None)))
        with self.assertRaises(ValueError):
            provider.recognize(FrameContext(image=object()), {"roi": [0, 0, 10]})
        with self.assertRaises(ValueError):
            provider.recognize(FrameContext(image=object()), {"unexpected": True})

    def test_missing_optional_backend_fails_only_when_recognition_is_requested(self):
        provider = RapidOcrProvider()
        with patch("core.perception.providers.rapidocr.import_module", side_effect=ModuleNotFoundError("missing")):
            with self.assertRaises(ProviderUnavailableError):
                provider.recognize(FrameContext(image=object()))

    def test_engine_options_are_applied_only_when_the_default_backend_is_first_needed(self):
        created_options = []

        class FakeDefaultRapidOcr:
            def __init__(self, **options):
                created_options.append(dict(options))

            def __call__(self, image, **kwargs):
                return ([[[[0, 0], [8, 0], [8, 6], [0, 6]], "Start", 0.9]], [0.01])

        fake_module = type("FakeRapidOcrModule", (), {"RapidOCR": FakeDefaultRapidOcr})
        provider = RapidOcrProvider(engine_options={"intra_op_num_threads": 4, "inter_op_num_threads": 1})
        self.assertEqual([], created_options)

        with patch("core.perception.providers.rapidocr.import_module", return_value=fake_module):
            spans = provider.recognize(FrameContext(image=object()))

        self.assertEqual([{"intra_op_num_threads": 4, "inter_op_num_threads": 1}], created_options)
        self.assertEqual("Start", spans[0].text)

    @unittest.skipUnless(importlib.util.find_spec("rapidocr_onnxruntime"), "RapidOCR optional dependency is not installed")
    def test_real_backend_finds_text_and_reports_its_image_location(self):
        import cv2
        import numpy as np

        image = np.full((260, 900, 3), 255, dtype=np.uint8)
        cv2.putText(image, "ENTER MAP", (80, 150), cv2.FONT_HERSHEY_SIMPLEX, 3, (0, 0, 0), 6, cv2.LINE_AA)
        spans = RapidOcrProvider().recognize(FrameContext(image=image))

        match = next((span for span in spans if "ENTER" in span.text.upper()), None)
        self.assertIsNotNone(match)
        assert match is not None
        self.assertGreater(match.bbox.width, 100.0)
        self.assertGreater(match.bbox.height, 20.0)
        self.assertGreater(match.bbox.center[0], 60.0)
        self.assertLess(match.bbox.center[0], 700.0)
        self.assertGreater(match.bbox.center[1], 40.0)
        self.assertLess(match.bbox.center[1], 210.0)


if __name__ == "__main__":
    unittest.main()
