"""Composition and platform adapters for action-event automation."""

from .host_bridge import HostEventBridge
from .hotkeys import HotkeyTriggerSource
from .models import EventWorkbenchStatus
from .service import EventWorkbenchService

__all__ = [
    "EventWorkbenchService",
    "EventWorkbenchStatus",
    "HostEventBridge",
    "HotkeyTriggerSource",
]
