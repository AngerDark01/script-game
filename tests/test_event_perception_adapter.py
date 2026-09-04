import unittest

from core.events.coordinator import EventCoordinator
from core.events.models import EventDetection, EventTick
from core.events.monitor import EventMonitor
from core.events.perception_adapter import (
    event_detection_to_target_detection,
    normalize_legacy_event_detections,
    target_detection_to_event_detection,
)
from core.events.registry import EventRegistry
from core.perception.models import BoundingBox, CoordinateSpace, TargetDetection
from core.shared.frame_registration import FrameRegistration


class _Config:
    enabled = True

    def __init__(self, events=None):
        self.events = events or {}

    def event(self, event_type):
        return self.events.get(event_type, {"enabled": True})


class _Detector:
    def __init__(self, detections):
        self.detections = detections
        self.calls = []

    def detect(self, tick, config):
        self.calls.append((tick, config))
        return list(self.detections)


class _Definition:
    def __init__(self, event_type, detector):
        self.event_type = event_type
        self.detector = detector

    def create_detector(self, config):
        return self.detector


class EventPerceptionAdapterTests(unittest.TestCase):
    def test_round_trip_preserves_minimap_event_data_without_shared_metadata(self):
        legacy = EventDetection(
            event_type="portal",
            confidence=0.83,
            detected_at_ms=1234,
            local_minimap_pos=(17, 29),
            source="minimap_shape_color",
            metadata={
                "bbox": [10, 20, 14, 18],
                "text": "入口",
                "nested": {"scores": [0.6, 0.83]},
            },
        )

        target = event_detection_to_target_detection(legacy)
        reconstructed = target_detection_to_event_detection(target, event_type="portal")

        self.assertEqual(CoordinateSpace.MINIMAP, target.coordinate_space)
        self.assertEqual((17.0, 29.0), target.center)
        self.assertEqual(BoundingBox(10.0, 20.0, 14.0, 18.0), target.bbox)
        self.assertEqual("入口", target.text)
        self.assertEqual(legacy, reconstructed)
        target.metadata["nested"]["scores"].append(1.0)
        reconstructed.metadata["nested"]["scores"].append(0.0)
        self.assertEqual([0.6, 0.83], legacy.metadata["nested"]["scores"])

    def test_generic_detection_requires_explicit_event_type_and_minimap_space(self):
        generic = TargetDetection(
            target_type="portal-icon",
            center=(52.2, 17.8),
            coordinate_space=CoordinateSpace.MINIMAP,
            confidence=0.5,
        )
        reconstructed = target_detection_to_event_detection(generic, event_type="portal")
        self.assertEqual("portal", reconstructed.event_type)
        self.assertEqual((52, 18), reconstructed.local_minimap_pos)
        with self.assertRaises(TypeError):
            target_detection_to_event_detection(generic)  # type: ignore[call-arg]
        with self.assertRaises(ValueError):
            target_detection_to_event_detection(
                TargetDetection(
                    target_type="portal-icon",
                    center=(52.0, 18.0),
                    coordinate_space=CoordinateSpace.FULL_SCREEN,
                    confidence=0.5,
                ),
                event_type="portal",
            )

    def test_normalizer_returns_equivalent_legacy_results_and_generic_debug_view(self):
        detections = (
            EventDetection("portal", 0.9, 1, (11, 12), source="portal", metadata={"bbox": [1, 2, 3, 4]}),
            EventDetection("loot", 0.7, 2, (21, 22), source="loot", metadata={"text": "稀有"}),
        )

        normalized, targets = normalize_legacy_event_detections(detections)

        self.assertEqual(detections, normalized)
        self.assertEqual(["portal", "loot"], [target.target_type for target in targets])
        self.assertEqual([CoordinateSpace.MINIMAP, CoordinateSpace.MINIMAP], [target.coordinate_space for target in targets])

    def test_monitor_normalizes_portal_and_loot_without_changing_detector_results(self):
        portal_detection = EventDetection("portal", 0.9, 50, (20, 30), source="portal", metadata={"nested": [1]})
        loot_detection = EventDetection("loot", 0.8, 50, (40, 50), source="loot", metadata={"bbox": [36, 46, 8, 8]})
        portal_detector = _Detector([portal_detection])
        loot_detector = _Detector([loot_detection])
        registry = EventRegistry()
        registry.register(_Definition("portal", portal_detector))
        registry.register(_Definition("loot", loot_detector))

        monitor = EventMonitor(registry)
        returned = monitor.detect(object(), _Config())

        self.assertEqual([portal_detection, loot_detection], returned)
        self.assertEqual(["portal", "loot"], [target.target_type for target in monitor.last_target_detections])
        monitor.last_target_detections[0].metadata["nested"].append(2)
        self.assertEqual([1], portal_detection.metadata["nested"])

    def test_coordinator_still_creates_a_pending_task_after_monitor_bridge(self):
        detection = EventDetection(
            "loot",
            0.8,
            100,
            (3, 4),
            source="minimap_weighted_blob",
            metadata={"candidate_count": 2},
        )
        registry = EventRegistry()
        registry.register(_Definition("loot", _Detector([detection])))
        config = _Config(
            {
                "loot": {
                    "enabled": True,
                    "stable_frames": 1,
                    "stable_variance": 0.0,
                    "localization_emit_interval_ms": 0,
                    "memory_confirm_frames": 1,
                    "priority": 60,
                }
            }
        )
        coordinator = EventCoordinator(registry, config)
        tick = EventTick(
            now_ms=100,
            frame_registration=FrameRegistration(
                valid=True,
                confidence=1.0,
                frame_origin_global=(100.0, 200.0),
            ),
        )

        coordinator.observe(tick)

        self.assertEqual([detection], coordinator.last_detections)
        self.assertEqual(["loot"], [target.target_type for target in coordinator.monitor.last_target_detections])
        self.assertEqual(1, len(tick.event_tasks))
        self.assertEqual("loot", tick.event_tasks[0].event_type)
        self.assertEqual((103, 204), tick.event_tasks[0].global_pos)
        self.assertEqual("pending", tick.event_tasks[0].state.value)


if __name__ == "__main__":
    unittest.main()
