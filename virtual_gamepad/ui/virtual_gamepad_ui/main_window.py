from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import QMainWindow

from .gamepad_page import GamepadPage


class MainWindow(QMainWindow):
    """Standalone diagnostic wrapper around the embeddable gamepad controls."""

    def __init__(
        self,
        client: Any,
        demo: bool = False,
        profile_path: Path | None = None,
        client_factory: Callable[[], Any] | None = None,
    ) -> None:
        super().__init__()
        self.client = client
        self.demo = demo
        self._close_requested = False
        self._close_approved = False
        default_profile = Path(__file__).resolve().parents[2] / "configs" / "controller-1.json"
        self.profile_path = profile_path or default_profile
        self.setWindowTitle("Virtual Gamepad")
        self.resize(1120, 700)
        self.page = GamepadPage(
            client,
            profile_root=self.profile_path,
            parent=self,
            demo=demo,
            client_factory=client_factory,
        )
        self.page.shutdown_finished.connect(self._on_page_shutdown_finished)
        self.setCentralWidget(self.page)

    def __getattr__(self, name: str) -> Any:
        """Keep the standalone diagnostic entry point source-compatible with prior callers."""
        page = self.__dict__.get("page")
        if page is not None and hasattr(page, name):
            return getattr(page, name)
        raise AttributeError(f"{type(self).__name__!s} has no attribute {name!r}")

    def closeEvent(self, event: QCloseEvent) -> None:
        if self._close_approved:
            event.accept()
            return
        # Do not let Qt tear down the event loop while reset/pause operations
        # are still in flight.  The page reports completion through a reusable
        # signal so a future workbench shell can use the same lifecycle fence.
        event.ignore()
        if not self._close_requested:
            self._close_requested = True
            self.page.shutdown()

    def _on_page_shutdown_finished(self, succeeded: bool, _message: str) -> None:
        if not succeeded:
            # The page keeps the actual error visible.  A later user close
            # request retries cleanup using a fresh client rather than exiting
            # with potentially locked input mappings.
            self._close_requested = False
            return
        self._close_approved = True
        self.close()
