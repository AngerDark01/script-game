"""Concrete event hook action instances."""

from .key_press import (
    DEFAULT_KEY_PRESS_HOOK_KEY,
    KEY_PRESS_HOOK_TYPE,
    KeyPressHookInstance,
    KeyPressHookSettings,
    key_press_settings_from_dict,
    key_press_settings_to_dict,
    normalized_key,
)

__all__ = [
    "DEFAULT_KEY_PRESS_HOOK_KEY",
    "KEY_PRESS_HOOK_TYPE",
    "KeyPressHookInstance",
    "KeyPressHookSettings",
    "key_press_settings_from_dict",
    "key_press_settings_to_dict",
    "normalized_key",
]

