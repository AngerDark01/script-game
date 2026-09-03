import unittest

from core.perception.algorithms.ocr_adapter import ProviderBackedOcrDetector
from core.perception.algorithms import ProviderBackedOcrDetector as PublicProviderBackedOcrDetector
from core.perception.builtins import create_default_algorithm_registry, create_ocr_detector
from core.perception import AlgorithmProfile, PerceptionEngine, TargetProfile
from core.perception.models import BoundingBox, CoordinateSpace, FrameContext
from core.perception.providers import OcrSpan, ProviderError


class MemoryOcrProvider:
    def __init__(self, spans):
        self.spans = tuple(spans)
        self.calls = []

    def recognize(self, frame, parameters=None):
        self.calls.append((frame, dict(parameters or {})))
        return self.spans


class FailingOcrProvider:
    def recognize(self, frame, parameters=None):
        raise ProviderError("OCR backend unavailable")


class OcrAdapterTests(unittest.TestCase):
    def test_adapter_is_available_from_algorithm_package_surface(self):
        self.assertIs(ProviderBackedOcrDetector, PublicProviderBackedOcrDetector)

    def test_matching_span_becomes_geometry_preserving_target_detection(self):
        frame = FrameContext(
            image=object(),
            captured_at_ms=4321,
            coordinate_space=CoordinateSpace.FULL_SCREEN,
        )
        expected_bbox = BoundingBox(18, 24, 80, 16)
        provider = MemoryOcrProvider(
            (
                OcrSpan("Enter Map", expected_bbox, CoordinateSpace.GAME_WINDOW, 0.93, language="en", metadata={"line": 2}),
                OcrSpan("Exit Map", BoundingBox(2, 3, 40, 12), CoordinateSpace.GAME_WINDOW, 0.98),
                OcrSpan("Enter Map", BoundingBox(5, 7, 50, 14), CoordinateSpace.GAME_WINDOW, 0.60),
            )
        )
        detector = ProviderBackedOcrDetector(
            target_type="map_entry",
            provider=provider,
            parameters={
                "text_query": "enter map",
                "min_ocr_confidence": 0.8,
                "provider_parameters": {"language": "en"},
            },
        )

        detections = detector.detect(frame)

        self.assertEqual([(frame, {"language": "en"})], provider.calls)
        self.assertEqual(1, len(detections))
        detection = detections[0]
        self.assertEqual("map_entry", detection.target_type)
        self.assertEqual(expected_bbox, detection.bbox)
        self.assertEqual(expected_bbox.center, detection.center)
        self.assertEqual(CoordinateSpace.GAME_WINDOW, detection.coordinate_space)
        self.assertEqual(0.93, detection.confidence)
        self.assertEqual("ocr", detection.source)
        self.assertEqual(4321, detection.detected_at_ms)
        self.assertEqual("Enter Map", detection.text)
        self.assertEqual("ocr", detection.evidence[0].algorithm_id)
        self.assertEqual("en", detection.evidence[0].details["language"])
        self.assertEqual(2, detection.evidence[0].details["line"])

    def test_contains_matching_can_be_case_sensitive_or_case_insensitive(self):
        frame = FrameContext(image=object())
        provider = MemoryOcrProvider(
            (
                OcrSpan("ENTER Portal", BoundingBox(0, 0, 10, 4), CoordinateSpace.FULL_SCREEN, 0.9),
                OcrSpan("enter portal", BoundingBox(20, 0, 10, 4), CoordinateSpace.FULL_SCREEN, 0.9),
                OcrSpan("Leave Portal", BoundingBox(40, 0, 10, 4), CoordinateSpace.FULL_SCREEN, 0.9),
            )
        )

        insensitive = ProviderBackedOcrDetector(
            target_type="portal_label",
            provider=provider,
            parameters={"text_query": "enter", "match_mode": "contains"},
        )
        sensitive = ProviderBackedOcrDetector(
            target_type="portal_label",
            provider=provider,
            parameters={"text_query": "ENTER", "match_mode": "contains", "case_sensitive": True},
        )

        self.assertEqual(["ENTER Portal", "enter portal"], [item.text for item in insensitive.detect(frame)])
        self.assertEqual(["ENTER Portal"], [item.text for item in sensitive.detect(frame)])

    def test_regex_matching_filters_spans_and_rejects_invalid_patterns(self):
        provider = MemoryOcrProvider(
            (
                OcrSpan("Tier 15", BoundingBox(0, 0, 10, 4), CoordinateSpace.FULL_SCREEN, 0.9),
                OcrSpan("Tier 9", BoundingBox(20, 0, 10, 4), CoordinateSpace.FULL_SCREEN, 0.9),
                OcrSpan("Map Tier", BoundingBox(40, 0, 10, 4), CoordinateSpace.FULL_SCREEN, 0.9),
            )
        )
        detector = ProviderBackedOcrDetector(
            target_type="tier_label",
            provider=provider,
            parameters={"text_query": r"^tier\s+(1[0-9])$", "match_mode": "regex"},
        )

        self.assertEqual(["Tier 15"], [item.text for item in detector.detect(FrameContext(image=object()))])
        with self.assertRaises(ValueError):
            ProviderBackedOcrDetector(
                target_type="tier_label",
                provider=provider,
                parameters={"text_query": "(", "match_mode": "regex"},
            )

    def test_configuration_rejects_invalid_confidence_bounds(self):
        provider = MemoryOcrProvider(())

        with self.assertRaises(ValueError):
            ProviderBackedOcrDetector(
                target_type="label",
                provider=provider,
                parameters={"text_query": "label", "min_ocr_confidence": 1.1},
            )
        with self.assertRaises(ValueError):
            ProviderBackedOcrDetector(
                target_type="label",
                provider=provider,
                parameters={"text_query": "label", "min_ocr_confidence": -0.1},
            )

    def test_max_results_keeps_the_strongest_matching_spans(self):
        provider = MemoryOcrProvider(
            (
                OcrSpan("Loot", BoundingBox(0, 0, 10, 4), CoordinateSpace.FULL_SCREEN, 0.61),
                OcrSpan("Loot", BoundingBox(20, 0, 10, 4), CoordinateSpace.FULL_SCREEN, 0.94),
                OcrSpan("Loot", BoundingBox(40, 0, 10, 4), CoordinateSpace.FULL_SCREEN, 0.83),
            )
        )
        detector = ProviderBackedOcrDetector(
            target_type="loot_label",
            provider=provider,
            parameters={"text_query": "loot", "max_results": 2},
        )

        self.assertEqual([0.94, 0.83], [item.confidence for item in detector.detect(FrameContext(image=object()))])
        with self.assertRaises(ValueError):
            ProviderBackedOcrDetector(
                target_type="loot_label",
                provider=provider,
                parameters={"text_query": "loot", "max_results": -1},
            )

    def test_ocr_descriptor_exposes_generic_profile_controls_without_bundling_backend(self):
        descriptor = create_default_algorithm_registry().descriptor("ocr")

        self.assertEqual("unavailable", descriptor.status)
        self.assertEqual(
            {"text_query", "match_mode", "case_sensitive", "min_ocr_confidence", "max_results"},
            {parameter.name for parameter in descriptor.parameters},
        )

    def test_provider_errors_and_invalid_raw_values_are_not_silently_normalized(self):
        parameters = {"text_query": "enter"}
        with self.assertRaises(ProviderError):
            ProviderBackedOcrDetector(
                target_type="label",
                provider=FailingOcrProvider(),
                parameters=parameters,
            ).detect(FrameContext(image=object()))
        with self.assertRaises(TypeError):
            ProviderBackedOcrDetector(
                target_type="label",
                provider=MemoryOcrProvider((object(),)),
                parameters=parameters,
            ).detect(FrameContext(image=object()))

    def test_factory_requires_explicit_provider_and_builds_adapter(self):
        provider = MemoryOcrProvider(())

        with self.assertRaises(ValueError):
            create_ocr_detector({"target_type": "label", "text_query": "Enter"})

        detector = create_ocr_detector(
            {"target_type": "label", "text_query": "Enter"},
            ocr_provider=provider,
        )

        self.assertIsInstance(detector, ProviderBackedOcrDetector)

    def test_engine_uses_runtime_provider_factory_without_serializing_provider(self):
        provider = MemoryOcrProvider(
            (OcrSpan("Start Trial", BoundingBox(12, 16, 70, 14), CoordinateSpace.VIEWPORT, 0.95),)
        )
        profile = TargetProfile(
            "game",
            "trial",
            "start_trial_label",
            (AlgorithmProfile("ocr", "ocr", {"text_query": "start trial"}),),
        )
        engine = PerceptionEngine(
            algorithm_factories={
                "ocr": lambda parameters: create_ocr_detector(parameters, ocr_provider=provider),
            }
        )

        result = engine.detect(FrameContext(image=object()), profile)

        self.assertEqual(1, len(result.detections))
        self.assertEqual("Start Trial", result.selected.text)
        self.assertNotIn("provider", profile.to_dict())
        self.assertEqual("start trial", profile.to_dict()["algorithms"][0]["parameters"]["text_query"])


if __name__ == "__main__":
    unittest.main()
