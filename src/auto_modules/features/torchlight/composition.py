"""Composition entry points for Torchlight business features."""

from auto_modules.core.events.registry import EventRegistry

from .loot import LootEventDefinition
from .portal import PortalEventDefinition


def register_torchlight_events(registry: EventRegistry | None = None) -> EventRegistry:
    """Register Torchlight event definitions into an existing event runtime.

    The caller owns the registry lifecycle; this function only assembles the
    feature definitions that belong to Torchlight.
    """
    target = registry if registry is not None else EventRegistry()
    target.register(PortalEventDefinition())
    target.register(LootEventDefinition())
    return target


def build_torchlight_feature_registry(*, registry: EventRegistry | None = None) -> EventRegistry:
    """Build the default Torchlight event registry for an application root."""
    return register_torchlight_events(registry)


__all__ = ["build_torchlight_feature_registry", "register_torchlight_events"]
