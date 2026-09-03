import unittest

import cv2
import numpy as np

from core.perception.algorithms.template_adapter import ProviderBackedTemplateDetector
from core.perception.algorithms import ProviderBackedTemplateDetector as PublicProviderBackedTemplateDetector
from core.perception.builtins import create_template_detector
from core.perception import AlgorithmProfile, FrameContext, PerceptionEngine, TargetProfile
from core.perception.models import CoordinateSpace
from core.perception.providers import TemplateResource, ProviderError


class MemoryTemplateProvider:
    def __init__(self, resource=None, error=None):
        self.resource = resource
        self.error = error
        self.loaded_ids = []

    def load(self, resource_id):
        self.loaded_ids.append(resource_id)
        if self.error is not None:
            raise self.error
        return self.resource


class TemplateAdapterTests(unittest.TestCase):
    def test_adapter_is_available_from_algorithm_package_surface(self):
        self.assertIs(ProviderBackedTemplateDetector, PublicProviderBackedTemplateDetector)

    def test_provider_resource_is_loaded_once_and_matches_like_existing_detector(self):
        image = np.zeros((80, 100, 3), dtype=np.uint8)
        cv2.rectangle(image, (35, 25), (55, 45), (255, 255, 255), -1)
        template = image[25:46, 35:56].copy()
        provider = MemoryTemplateProvider(TemplateResource("device", image=template, source="fixture"))
        frame = FrameContext(image=image, coordinate_space=CoordinateSpace.FULL_SCREEN)

        detector = ProviderBackedTemplateDetector(
            target_type="map_device",
            provider=provider,
            resource_id="device",
            parameters={"threshold": 0.85, "top_k": 1},
        )
        detections = detector.detect(frame)

        self.assertEqual(["device"], provider.loaded_ids)
        self.assertEqual(1, len(detections))
        self.assertEqual("map_device", detections[0].target_type)
        self.assertEqual("template", detections[0].source)
        self.assertIsNotNone(detections[0].bbox)
        self.assertAlmostEqual(45.0, detections[0].center[0], delta=2.0)
        self.assertAlmostEqual(35.0, detections[0].center[1], delta=2.0)

    def test_adapter_rejects_empty_id_invalid_provider_and_invalid_resource(self):
        resource = TemplateResource("device", image=np.ones((4, 4, 3), dtype=np.uint8))
        with self.assertRaises(ValueError):
            ProviderBackedTemplateDetector(target_type="target", provider=MemoryTemplateProvider(resource), resource_id="")
        with self.assertRaises(TypeError):
            ProviderBackedTemplateDetector(target_type="target", provider=object(), resource_id="device")
        with self.assertRaises(TypeError):
            ProviderBackedTemplateDetector(
                target_type="target",
                provider=MemoryTemplateProvider(object()),
                resource_id="device",
            )

    def test_provider_error_is_not_silently_replaced_by_path_fallback(self):
        provider = MemoryTemplateProvider(error=ProviderError("backend unavailable"))

        with self.assertRaises(ProviderError):
            ProviderBackedTemplateDetector(target_type="target", provider=provider, resource_id="device")
        self.assertEqual(["device"], provider.loaded_ids)

    def test_factory_composes_resource_id_only_with_explicit_provider(self):
        template = np.ones((8, 8, 3), dtype=np.uint8)
        provider = MemoryTemplateProvider(TemplateResource("device", image=template))

        detector = create_template_detector(
            {"target_type": "map_device", "template_resource_id": "device", "threshold": 0.9},
            template_provider=provider,
        )

        self.assertIsInstance(detector, ProviderBackedTemplateDetector)
        self.assertEqual(["device"], provider.loaded_ids)

    def test_factory_preserves_array_and_path_compatibility_and_rejects_ambiguity(self):
        template = np.ones((8, 8, 3), dtype=np.uint8)

        direct = create_template_detector({"target_type": "target", "template": template})
        self.assertNotIsInstance(direct, ProviderBackedTemplateDetector)

        with self.assertRaises(ValueError):
            create_template_detector({"target_type": "target", "template_resource_id": "device"})
        with self.assertRaises(ValueError):
            create_template_detector({"target_type": "target", "template": template, "template_resource_id": "device"})
        with self.assertRaises(ValueError):
            create_template_detector({"target_type": "target"})

    def test_engine_accepts_runtime_factory_without_serializing_provider(self):
        image = np.zeros((40, 50, 3), dtype=np.uint8)
        cv2.rectangle(image, (15, 10), (25, 20), (255, 255, 255), -1)
        template = image[10:21, 15:26].copy()
        provider = MemoryTemplateProvider(TemplateResource("device", image=template))
        profile = TargetProfile(
            "game",
            "scene",
            "map_device",
            (AlgorithmProfile("template", "template", {"template_resource_id": "device", "threshold": 0.85}),),
        )
        engine = PerceptionEngine(
            algorithm_factories={
                "template": lambda parameters: create_template_detector(parameters, template_provider=provider),
            }
        )

        result = engine.detect(FrameContext(image=image), profile)

        self.assertEqual(1, len(result.detections))
        self.assertEqual(["device"], provider.loaded_ids)
        self.assertNotIn("provider", profile.to_dict())
        self.assertEqual("device", profile.to_dict()["algorithms"][0]["parameters"]["template_resource_id"])

    def test_default_engine_reports_missing_provider_for_resource_id_profile(self):
        profile = TargetProfile(
            "game",
            "scene",
            "map_device",
            (AlgorithmProfile("template", "template", {"template_resource_id": "device"}),),
        )

        result = PerceptionEngine().detect(FrameContext(image=np.zeros((8, 8, 3), dtype=np.uint8)), profile)

        self.assertEqual((), result.detections)
        self.assertIn("template", result.errors)


if __name__ == "__main__":
    unittest.main()
