from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QWidget


def toggle_owned_dialog(dialog: QWidget | None, owner: QWidget | None = None) -> bool:
    """Show an owned dialog, or return True when the active dialog should be hidden."""
    if dialog is None:
        return False
    if dialog.isVisible() and dialog.isActiveWindow():
        return True
    show_owned_dialog(dialog, owner)
    return False


def show_owned_dialog(dialog: QWidget | None, owner: QWidget | None = None) -> None:
    if dialog is None:
        return
    _restore_unminimized(dialog)
    if owner is not None and not dialog.isVisible():
        base = owner.frameGeometry()
        dialog.move(base.x() + 80, base.y() + 80)
    dialog.show()
    _restore_unminimized(dialog)
    dialog.raise_()
    dialog.activateWindow()
    QApplication.setActiveWindow(dialog)


def _restore_unminimized(dialog: QWidget) -> None:
    if dialog.windowState() & Qt.WindowMinimized:
        dialog.setWindowState(dialog.windowState() & ~Qt.WindowMinimized)
