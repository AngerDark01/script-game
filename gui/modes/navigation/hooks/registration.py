from __future__ import annotations

from collections.abc import Callable

from core.events.hooks.instances import (
    KEY_PRESS_HOOK_TYPE,
    KeyPressHookInstance,
    key_press_settings_from_dict,
)


class NavigationHookRuntime:
    """Register configured event hook instances against the navigation controller."""

    def __init__(
        self,
        *,
        navigation_task_controller,
        motion_controller,
        enable_game_input_mode: Callable[[], None],
    ) -> None:
        self.navigation_task_controller = navigation_task_controller
        self.motion_controller = motion_controller
        self.enable_game_input_mode = enable_game_input_mode
        self._unsubscribers: list[Callable[[], object]] = []

    def apply_event_config(self, event_config) -> int:
        self.clear()
        if event_config is None:
            return 0
        registered = 0
        for instance_config in _hook_instances(event_config):
            if str(instance_config.get("type") or "") != KEY_PRESS_HOOK_TYPE:
                continue
            settings = key_press_settings_from_dict(instance_config)
            if not settings.enabled or not settings.key or not settings.event_types or not settings.triggers:
                continue
            handler = KeyPressHookInstance(settings, self._press_key_once)
            for trigger in settings.triggers:
                self._unsubscribers.append(
                    self.navigation_task_controller.event_hooks.register(trigger, handler)
                )
                registered += 1
        return registered

    def clear(self) -> None:
        while self._unsubscribers:
            unsubscribe = self._unsubscribers.pop()
            unsubscribe()

    def _press_key_once(self, key: str, reason: str) -> object:
        self.enable_game_input_mode()
        self.motion_controller.set_control_enabled(True)
        return self.motion_controller.press_key(key, reason=reason)


def _hook_instances(event_config) -> list[dict]:
    hooks = getattr(event_config, "hooks", None)
    if not isinstance(hooks, dict):
        return []
    instances = hooks.get("instances", [])
    if not isinstance(instances, list):
        return []
    return [item for item in instances if isinstance(item, dict)]
