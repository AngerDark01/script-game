from PySide6.QtCore import Signal
from PySide6.QtWidgets import QPushButton, QMenu


GAMEPAD_BUTTONS = (
    'A', 'B', 'X', 'Y', 'LB', 'RB', 'LS', 'RS',
    'UP', 'DOWN', 'LEFT', 'RIGHT', 'START', 'BACK',
)


class GamepadButtonPicker(QPushButton):
    """Compact checkable menu for selecting one or more Xbox buttons."""

    selectionChanged = Signal(object)

    def __init__(self, buttons=(), parent=None):
        super().__init__(parent)
        self._buttons = tuple()
        self._menu = QMenu(self)
        for name in GAMEPAD_BUTTONS:
            action = self._menu.addAction(name)
            action.setCheckable(True)
            action.toggled.connect(self._changed)
        self.setMenu(self._menu)
        self.setMinimumWidth(130)
        self.set_buttons(buttons)

    def buttons(self):
        return self._buttons

    def set_buttons(self, buttons):
        wanted = set(buttons or ())
        for action in self._menu.actions():
            action.blockSignals(True)
            action.setChecked(action.text() in wanted)
            action.blockSignals(False)
        self._sync()

    def _changed(self, _checked):
        self._sync()
        self.selectionChanged.emit(self._buttons)

    def _sync(self):
        self._buttons = tuple(a.text() for a in self._menu.actions() if a.isChecked())
        self.setText(' + '.join(self._buttons) if self._buttons else '选择手柄按键')
