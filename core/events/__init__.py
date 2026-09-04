"""Event system package.

The navigation loop talks to this package through EventCoordinator. Concrete
events such as portal remain isolated under core.events.types.
"""

from .hooks import (
    EVENT_HOOK_COMPLETED,
    EVENT_HOOK_VISIBLE_TARGET,
    EventHookContext,
    EventHookHandler,
    EventHookRegistry,
)
from .perception_adapter import (
    event_detection_to_target_detection,
    normalize_legacy_event_detections,
    target_detection_to_event_detection,
)

__all__ = [
    "EVENT_HOOK_COMPLETED",
    "EVENT_HOOK_VISIBLE_TARGET",
    "EventHookContext",
    "EventHookHandler",
    "EventHookRegistry",
    "event_detection_to_target_detection",
    "normalize_legacy_event_detections",
    "target_detection_to_event_detection",
]
