"""Compatibility facade for event configuration."""

import copy

from .config_io import event_config_path, load_event_config, save_event_config
from .config_model import DEFAULT_EVENT_CONFIG, EventSystemConfig


def apply_registered_event_defaults(registry, config: EventSystemConfig) -> EventSystemConfig:
    """Materialize each registered definition's defaults into a config.

    The event system stays game-neutral: concrete definitions own their
    defaults, while this helper only applies the common registry contract.
    Persisted values always override defaults and unknown values are retained.
    """
    for definition in registry.definitions():
        event_type = str(definition.event_type)
        defaults = (
            definition.default_config()
            if hasattr(definition, "default_config")
            else {}
        )
        current = config.event(event_type) or {}
        config.events[event_type] = _deep_merge_dicts(defaults, current)
    return config


def build_tui_event_options(registry, config: EventSystemConfig) -> list[dict]:
    """Return complete event options for a TUI/config surface."""
    apply_registered_event_defaults(registry, config)
    options = []
    for definition in registry.definitions():
        current = config.event(definition.event_type)
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


def _deep_merge_dicts(defaults: dict, override: dict) -> dict:
    result = copy.deepcopy(defaults or {})
    for key, value in (override or {}).items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _deep_merge_dicts(result[key], value)
        else:
            result[key] = copy.deepcopy(value)
    return result


__all__ = [
    "DEFAULT_EVENT_CONFIG",
    "EventSystemConfig",
    "apply_registered_event_defaults",
    "build_tui_event_options",
    "event_config_path",
    "load_event_config",
    "save_event_config",
]
