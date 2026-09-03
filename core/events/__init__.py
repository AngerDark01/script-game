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

__all__ = [
    "EVENT_HOOK_COMPLETED",
    "EVENT_HOOK_VISIBLE_TARGET",
    "EventHookContext",
    "EventHookHandler",
    "EventHookRegistry",
]
