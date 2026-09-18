"""Composition and platform adapters for action-event automation."""

from .host_bridge import HostEventBridge
from .hotkeys import HotkeyTriggerSource

__all__ = ["HostEventBridge", "HotkeyTriggerSource"]
