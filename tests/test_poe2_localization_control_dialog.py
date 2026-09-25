import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from auto_modules.ui.modes.poe2_live_terrain.localization_control_dialog import (
    Poe2LocalizationControlDialog,
)


def _app():
    return QApplication.instance() or QApplication([])


def test_control_dialog_is_non_modal_and_enables_both_strategies_by_default():
    _app()
    dialog = Poe2LocalizationControlDialog()
    try:
        assert dialog.isModal() is False
        assert dialog.panel.strategy_a_check.isChecked()
        assert dialog.panel.strategy_b_check.isChecked()
        assert not dialog.panel.start_button.isEnabled()

        dialog.set_ready(True)
        assert dialog.panel.start_button.isEnabled()
    finally:
        dialog.close()


def test_closing_control_dialog_does_not_emit_stop():
    _app()
    dialog = Poe2LocalizationControlDialog()
    stopped = []
    dialog.panel.stop_requested.connect(lambda: stopped.append(True))
    dialog.close()
    assert stopped == []
