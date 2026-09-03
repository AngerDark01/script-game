from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from ..presentation import toggle_owned_dialog
from .panel_adapter import (
    connect_event_dialog_signals,
    create_event_dialog,
    refresh_event_dialog,
)


@dataclass(frozen=True)
class NavigationEventDialogLifecycleTargets:
    parent: object
    main_window: object
    get_event_dialog: Callable[[], object]
    set_event_dialog: Callable[[object], None]
    get_portal_test_controller: Callable[[], object]
    get_event_registry: Callable[[], object]
    get_event_config: Callable[[], object]
    get_event_coordinator: Callable[[], object]
    get_map_name: Callable[[], str]
    on_config_changed: Callable[[object], None]
    on_save_requested: Callable[[], None]
    on_test_portal_requested: Callable[[], None]
    on_reset_portal_requested: Callable[[], None]
    on_reset_events_requested: Callable[[], None]


class NavigationEventDialogLifecycle:
    """Own event dialog creation, signal wiring, refresh, and toggle behaviour."""

    def __init__(self, targets: NavigationEventDialogLifecycleTargets) -> None:
        self.targets = targets

    def ensure_dialog(self):
        dialog = self.targets.get_event_dialog()
        if dialog is not None:
            return dialog

        dialog = create_event_dialog(self.targets.main_window or self.targets.parent)
        self.targets.set_event_dialog(dialog)
        self.connect_signals()
        self._sync_manual_test_button(dialog)
        if self.targets.get_event_registry() and self.targets.get_event_config() is not None:
            self.refresh_dialog()
        return dialog

    def connect_signals(self) -> None:
        connect_event_dialog_signals(
            self.targets.get_event_dialog(),
            on_config_changed=self.targets.on_config_changed,
            on_save_requested=self.targets.on_save_requested,
            on_test_portal_requested=self.targets.on_test_portal_requested,
            on_reset_portal_requested=self.targets.on_reset_portal_requested,
            on_reset_events_requested=self.targets.on_reset_events_requested,
        )

    def toggle_dialog(self) -> None:
        dialog = self.ensure_dialog()
        self.refresh_dialog()
        if toggle_owned_dialog(dialog, self.targets.main_window):
            dialog.hide()

    def refresh_dialog(self) -> None:
        refresh_event_dialog(
            self.targets.get_event_dialog(),
            event_registry=self.targets.get_event_registry(),
            event_config=self.targets.get_event_config(),
            event_coordinator=self.targets.get_event_coordinator(),
            map_name=self.targets.get_map_name(),
        )

    def refresh_tasks(self) -> None:
        dialog = self.targets.get_event_dialog()
        if dialog:
            dialog.refresh_tasks()

    def _sync_manual_test_button(self, dialog) -> None:
        portal_test_controller = self.targets.get_portal_test_controller()
        if portal_test_controller is None:
            return
        portal_test_controller.button = dialog.test_portal_button
        portal_test_controller.reset_button()
