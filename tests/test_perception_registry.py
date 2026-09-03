import unittest

from core.perception.algorithms.base import AlgorithmDescriptor, ParameterSpec
from core.perception.models import CoordinateSpace
from core.perception.registry import AlgorithmRegistry


class PerceptionRegistryTests(unittest.TestCase):
    def test_registry_creates_algorithm_with_copied_parameters(self):
        registry = AlgorithmRegistry()
        descriptor = AlgorithmDescriptor(
            algorithm_id="fake",
            display_name="Fake detector",
            supported_spaces=(CoordinateSpace.FULL_SCREEN,),
            parameters=(ParameterSpec("threshold", "Threshold", "float", 0.5, 0.0, 1.0),),
        )
        received = {}

        def factory(parameters):
            received.update(parameters)
            return object()

        registry.register(descriptor, factory)
        params = {"threshold": 0.8}
        self.assertIsNotNone(registry.create("fake", params))
        params["threshold"] = 0.1
        self.assertEqual(0.8, received["threshold"])

    def test_duplicate_ids_are_rejected_and_descriptors_are_listed(self):
        registry = AlgorithmRegistry()
        descriptor = AlgorithmDescriptor("fake", "Fake detector")
        registry.register(descriptor, lambda _: object())

        with self.assertRaises(ValueError):
            registry.register(descriptor, lambda _: object())

        self.assertEqual(["fake"], [item.algorithm_id for item in registry.descriptors()])

    def test_unavailable_algorithm_is_visible_but_cannot_be_created(self):
        registry = AlgorithmRegistry()
        descriptor = AlgorithmDescriptor("ocr", "OCR", status="unavailable")
        registry.register(descriptor, None)

        self.assertEqual("unavailable", registry.descriptor("ocr").status)
        with self.assertRaises(RuntimeError):
            registry.create("ocr")

    def test_parameter_spec_validates_ranges_and_serializes_for_gui(self):
        spec = ParameterSpec("threshold", "Threshold", "float", 0.5, 0.0, 1.0)

        self.assertEqual("threshold", spec.to_dict()["name"])
        with self.assertRaises(ValueError):
            ParameterSpec("bad", "Bad", "float", 2.0, 0.0, 1.0)


if __name__ == "__main__":
    unittest.main()
