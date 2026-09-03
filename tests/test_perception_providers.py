import unittest

from core.perception.models import BoundingBox, CoordinateSpace, FrameContext
from core.perception.providers import (
    FeatureBackend,
    FeatureMatch,
    FrameSource,
    OcrProvider,
    OcrSpan,
    ProviderCapability,
    ProviderCapabilityMismatchError,
    create_default_provider_registry,
    ProviderDescriptor,
    ProviderRegistrationError,
    ProviderRegistry,
    ProviderUnavailableError,
    TemplateResource,
    TemplateResourceProvider,
    UnknownProviderError,
)


class ProviderContractTests(unittest.TestCase):
    def test_descriptor_is_discoverable_and_defensively_serialized(self):
        descriptor = ProviderDescriptor(
            "ocr.local",
            "Local OCR",
            ProviderCapability.OCR,
            status="unavailable",
            metadata={"install_hint": "Install an OCR backend"},
        )

        payload = descriptor.to_dict()
        payload["metadata"]["install_hint"] = "changed"

        self.assertEqual("ocr", payload["capability"])
        self.assertEqual("unavailable", payload["status"])
        self.assertEqual("Install an OCR backend", descriptor.metadata["install_hint"])

    def test_raw_provider_dtos_preserve_evidence_without_target_semantics(self):
        resource = TemplateResource("assets/map-device", image=object(), source="fixture")
        span = OcrSpan(
            "Enter",
            BoundingBox(2, 3, 20, 8),
            CoordinateSpace.GAME_WINDOW,
            0.91,
            language="en",
        )
        match = FeatureMatch(
            "assets/map-device",
            frame_point=(100.0, 120.0),
            resource_point=(12.0, 18.0),
            confidence=0.82,
        )

        self.assertEqual("assets/map-device", resource.resource_id)
        self.assertEqual("Enter", span.text)
        self.assertEqual((100.0, 120.0), match.frame_point)
        self.assertFalse(hasattr(span, "target_type"))

    def test_contract_protocols_are_importable_without_runtime_backends(self):
        self.assertTrue(hasattr(FrameSource, "capture"))
        self.assertTrue(hasattr(TemplateResourceProvider, "load"))
        self.assertTrue(hasattr(OcrProvider, "recognize"))
        self.assertTrue(hasattr(FeatureBackend, "match"))
        self.assertIsNotNone(FrameContext)

    def test_contracts_reject_invalid_ids_statuses_and_confidences(self):
        with self.assertRaises(ValueError):
            ProviderDescriptor("", "Missing", ProviderCapability.OCR)
        with self.assertRaises(ValueError):
            ProviderDescriptor("ocr.local", "Local OCR", ProviderCapability.OCR, status="installed")
        with self.assertRaises(ValueError):
            TemplateResource("", image=object())
        with self.assertRaises(ValueError):
            OcrSpan("text", BoundingBox(0, 0, 1, 1), CoordinateSpace.FULL_SCREEN, 1.1)


class ProviderRegistryTests(unittest.TestCase):
    def test_registry_resolves_only_the_requested_capability(self):
        registry = ProviderRegistry()
        provider = object()
        descriptor = ProviderDescriptor(
            "templates.memory",
            "Memory templates",
            ProviderCapability.TEMPLATE_RESOURCE,
        )
        registry.register(descriptor, provider)

        resolved = registry.resolve("templates.memory", ProviderCapability.TEMPLATE_RESOURCE)

        self.assertIs(provider, resolved)
        self.assertEqual([descriptor], registry.descriptors(ProviderCapability.TEMPLATE_RESOURCE))
        self.assertEqual([], registry.descriptors(ProviderCapability.OCR))

    def test_registry_exposes_explicit_resolution_and_registration_errors(self):
        registry = ProviderRegistry()
        unavailable = ProviderDescriptor(
            "ocr.optional",
            "Optional OCR",
            ProviderCapability.OCR,
            status="unavailable",
        )
        registry.register(unavailable, None)

        with self.assertRaises(UnknownProviderError):
            registry.resolve("missing")
        with self.assertRaises(ProviderCapabilityMismatchError):
            registry.resolve("ocr.optional", ProviderCapability.FEATURE_BACKEND)
        with self.assertRaises(ProviderUnavailableError):
            registry.resolve("ocr.optional", ProviderCapability.OCR)
        with self.assertRaises(ProviderRegistrationError):
            registry.register(ProviderDescriptor("frame.required", "Frame", ProviderCapability.FRAME_SOURCE), None)
        with self.assertRaises(ProviderRegistrationError):
            registry.register(unavailable, None)


class DefaultProviderCatalogTests(unittest.TestCase):
    def test_default_catalog_lists_uninstalled_capabilities_without_resolving_them(self):
        registry = create_default_provider_registry()

        descriptors = {descriptor.provider_id: descriptor for descriptor in registry.descriptors()}

        self.assertEqual(ProviderCapability.FRAME_SOURCE, descriptors["frame.screen"].capability)
        self.assertEqual(ProviderCapability.TEMPLATE_RESOURCE, descriptors["template.resource"].capability)
        self.assertEqual(ProviderCapability.OCR, descriptors["ocr.default"].capability)
        self.assertEqual(ProviderCapability.FEATURE_BACKEND, descriptors["feature.default"].capability)
        self.assertTrue(all(descriptor.status == "unavailable" for descriptor in descriptors.values()))
        with self.assertRaises(ProviderUnavailableError):
            registry.resolve("ocr.default", ProviderCapability.OCR)


if __name__ == "__main__":
    unittest.main()
