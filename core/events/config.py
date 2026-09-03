"""Compatibility facade for event configuration."""

from .config_io import event_config_path, load_event_config, save_event_config
from .config_model import DEFAULT_EVENT_CONFIG, EventSystemConfig


def build_tui_event_options(registry, config: EventSystemConfig) -> list[dict]:
    """Return complete event options for a TUI/config surface."""
    options = []
    for definition in registry.definitions():
        current = {
            **(definition.default_config() if hasattr(definition, "default_config") else {}),
            **(config.event(definition.event_type) or {}),
        }
        config.events[definition.event_type] = current
        options.append(
            {
                "event_type": definition.event_type,
                "display_name": definition.display_name,
                "description": getattr(definition, "description", ""),
                "enabled": bool(current.get("enabled", True)),
                "schema": definition.config_schema(),
                "current_values": current,
            }
        )
    return options


__all__ = [
    "DEFAULT_EVENT_CONFIG",
    "EventSystemConfig",
    "build_tui_event_options",
    "event_config_path",
    "load_event_config",
    "save_event_config",
]
