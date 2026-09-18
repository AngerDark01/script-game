"""Adapters for the local virtual-gamepad Host."""

from .event_bridge import HostEventBridge
from .follow_transport import FollowTransport

__all__ = ["FollowTransport", "HostEventBridge"]
