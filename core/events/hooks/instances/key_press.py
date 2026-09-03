from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from core.events.debug import event_log
from core.events.hooks.models import EventHookContext, EVENT_HOOK_NAMES


KEY_PRESS_HOOK_TYPE = "key_press"
DEFAULT_KEY_PRESS_HOOK_KEY = "d"


@dataclass(frozen=True)
class KeyPressHookSettings:
    instance_id: str
    name: str
    key: str
    event_types: tuple[str, ...]
    triggers: tuple[str, ...]
    enabled: bool = True


class KeyPressHookInstance:
    """A hook action that presses one configured key once."""

    def __init__(
        self,
        settings: KeyPressHookSettings,
        press_key: Callable[[str, str], object],
    ) -> None:
        self.settings = settings
        self._press_key = press_key

    def __call__(self, context: EventHookContext) -> None:
        if not self.settings.enabled or context.hook_name not in self.settings.triggers:
            return
        if not _matches_event_type(self.settings.event_types, context.event_type):
            return
        key = normalized_key(self.settings.key)
        if not key:
            event_log(
                "key hook skipped",
                hook=context.hook_name,
                instance=self.settings.instance_id,
                reason="empty key",
            )
            return
        reason = f"hook:{self.settings.instance_id}:{context.hook_name}:{context.event_type}"
        self._press_key(key, reason)
        event_log(
            "key hook pressed",
            hook=context.hook_name,
            instance=self.settings.instance_id,
            event=context.event_type,
            key=key,
        )


def key_press_settings_from_dict(data: dict) -> KeyPressHookSettings:
    raw_triggers = data.get("triggers", [])
    if isinstance(raw_triggers, str):
        raw_triggers = [raw_triggers]
    triggers = tuple(
        trigger
        for trigger in (str(item or "").strip() for item in raw_triggers or [])
        if trigger in EVENT_HOOK_NAMES
    )
    event_types = tuple(
        item
        for item in (str(value or "").strip() for value in _raw_list(data, "event_types", fallback_key="event_type"))
        if item
    )
    instance_id = str(data.get("id") or "").strip() or "key_press"
    return KeyPressHookSettings(
        instance_id=instance_id,
        name=str(data.get("name") or "按键 Hook"),
        key=normalized_key(data.get("key", DEFAULT_KEY_PRESS_HOOK_KEY)),
        event_types=event_types,
        triggers=triggers,
        enabled=bool(data.get("enabled", True)),
    )


def key_press_settings_to_dict(settings: KeyPressHookSettings) -> dict:
    return {
        "id": settings.instance_id,
        "type": KEY_PRESS_HOOK_TYPE,
        "name": settings.name,
        "enabled": bool(settings.enabled),
        "key": normalized_key(settings.key),
        "event_types": list(settings.event_types),
        "triggers": list(settings.triggers),
    }


def normalized_key(key) -> str:
    return str(key or "").strip().lower()


def _raw_list(data: dict, key: str, *, fallback_key: str | None = None) -> list:
    value = data.get(key)
    if value is None and fallback_key:
        value = data.get(fallback_key)
    if isinstance(value, str):
        return [value]
    if isinstance(value, list) or isinstance(value, tuple):
        return list(value)
    return []


def _matches_event_type(event_types: tuple[str, ...], event_type: str) -> bool:
    if not event_types:
        return False
    return str(event_type or "").strip() in event_types
