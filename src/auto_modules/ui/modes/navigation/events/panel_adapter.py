from __future__ import annotations

from ..event_adapter import event_config_summary
from ....dialogs.event_manager_dialog import EventManagerDialog


def create_event_dialog(parent) -> EventManagerDialog:
    return EventManagerDialog(parent)


def connect_event_dialog_signals(
    dialog: EventManagerDialog | None,
    *,
    on_config_changed,
    on_save_requested,
    on_test_portal_requested,
    on_reset_portal_requested,
    on_reset_events_requested,
) -> None:
    if dialog is None:
        return
    _connect_once(dialog, "config_changed", dialog.config_changed, on_config_changed)
    _connect_once(dialog, "save_requested", dialog.save_requested, on_save_requested)
    _connect_once(dialog, "test_portal_requested", dialog.test_portal_requested, on_test_portal_requested)
    _connect_once(dialog, "reset_portal_requested", dialog.reset_portal_requested, on_reset_portal_requested)
    _connect_once(dialog, "reset_events_requested", dialog.reset_events_requested, on_reset_events_requested)


def refresh_event_dialog(
    dialog: EventManagerDialog | None,
    *,
    event_registry,
    event_config,
    event_coordinator,
    map_name: str,
) -> None:
    if dialog is None:
        return
    dialog.set_context(
        event_registry,
        event_config,
        event_coordinator,
        map_name,
    )


def summarize_event_config(event_config) -> str:
    return event_config_summary(event_config)


def _connect_once(dialog, key: str, signal, slot) -> None:
    slots = getattr(dialog, "_navigation_event_signal_slots", None)
    if not isinstance(slots, dict):
        slots = {}
        setattr(dialog, "_navigation_event_signal_slots", slots)
    previous_slot = slots.get(key)
    if previous_slot == slot:
        return
    if previous_slot is not None:
        try:
            signal.disconnect(previous_slot)
        except (RuntimeError, TypeError):
            pass
    signal.connect(slot)
    slots[key] = slot
