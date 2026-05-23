from __future__ import annotations


class ManualEventTestController:
    """Keeps a manual event-test button in sync with runtime state."""

    def __init__(self, button, start_text: str, stop_text: str):
        self.button = button
        self.start_text = start_text
        self.stop_text = stop_text
        self.active = False
        self._sync_button()

    def start(self) -> None:
        self.active = True
        self._sync_button()

    def stop(self) -> None:
        self.active = False
        self._sync_button()

    def reset_button(self) -> None:
        self._sync_button()

    def _sync_button(self) -> None:
        if self.button is None:
            return
        self.button.setText(self.stop_text if self.active else self.start_text)
        if self.button.isChecked() != self.active:
            self.button.setChecked(self.active)
